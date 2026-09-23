import assert from 'node:assert/strict';
import test from 'node:test';

import { ServiceNowApiError } from '../src/errors.js';
import { fetchSyslogRecords, registerAnalyzeSyslogTool } from '../src/tools/analyze-syslog.js';
import { ALLOWED_CRUD_TABLES } from '../src/tools/allowed-crud-tables.js';
import { analyzeSyslogRecords, normalizeMessage } from '../src/tools/syslog-analysis.js';
import { parseDateInput, resolveSyslogDateRange } from '../src/tools/syslog-date-range.js';

const NOW = new Date(2026, 8, 23, 12, 0, 0);

function registerTool() {
  let tool;
  const server = {
    tool(name, description, schema, handler) {
      tool = { name, description, schema, handler };
    }
  };

  // The stub executeTool runs the operation against a client that only supports reads.
  return { server, get tool() { return tool; } };
}

function createReadOnlyClient(pages, calls) {
  const writeMethod = (name) => async () => {
    throw new Error(`${name} must never be called by analyze_syslog`);
  };

  return {
    async queryTableRecords(request) {
      calls.push(request);
      return pages.shift() ?? [];
    },
    createTableRecord: writeMethod('createTableRecord'),
    updateTableRecord: writeMethod('updateTableRecord'),
    deleteTableRecord: writeMethod('deleteTableRecord')
  };
}

test('parseDateInput accepts natural language date formats', () => {
  const expected = { year: 2026, month: 9, day: 23 };

  for (const input of [
    '09/23/2026',
    '9/23/2026',
    '2026-09-23',
    'Sept 23, 2026',
    'September 23, 2026',
    'sep 23 2026',
    'Sep. 23rd, 2026',
    '23 September 2026',
    '9-23-2026'
  ]) {
    assert.deepEqual(parseDateInput(input, NOW), expected, input);
  }
});

test('parseDateInput assumes the current year when none is given', () => {
  assert.deepEqual(parseDateInput('Sept 5', NOW), { year: 2026, month: 9, day: 5 });
  assert.deepEqual(parseDateInput('9/5', NOW), { year: 2026, month: 9, day: 5 });
  assert.deepEqual(parseDateInput('5 March', NOW), { year: 2026, month: 3, day: 5 });
});

test('parseDateInput supports today and yesterday', () => {
  assert.deepEqual(parseDateInput('today', NOW), { year: 2026, month: 9, day: 23 });
  assert.deepEqual(parseDateInput('Yesterday', NOW), { year: 2026, month: 9, day: 22 });
});

test('parseDateInput rejects unparseable and impossible dates', () => {
  assert.throws(() => parseDateInput('sometime soon', NOW), /Could not understand/);
  assert.throws(() => parseDateInput('13/40/2026', NOW), /not a real calendar date/);
  assert.throws(() => parseDateInput('02/30/2026', NOW), /not a real calendar date/);
  assert.throws(() => parseDateInput('Foo 12', NOW), /Could not understand/);
});

test('resolveSyslogDateRange builds an inclusive range and enforces the 2 week limit', () => {
  const range = resolveSyslogDateRange('09/10/2026', 'Sept 23, 2026', NOW);
  assert.equal(range.days, 14);
  assert.equal(range.startDateTime, '2026-09-10 00:00:00');
  assert.equal(range.endDateTime, '2026-09-23 23:59:59');

  assert.throws(() => resolveSyslogDateRange('09/09/2026', '09/23/2026', NOW), /15 days/);
  assert.throws(() => resolveSyslogDateRange('09/23/2026', '09/22/2026', NOW), /before the start date/);
  assert.equal(resolveSyslogDateRange('09/23/2026', '09/23/2026', NOW).days, 1);
});

test('analyze_syslog asks for missing dates without touching ServiceNow', async () => {
  const registration = registerTool();
  let executeCount = 0;
  registerAnalyzeSyslogTool(registration.server, async () => {
    executeCount += 1;
  });

  const result = await registration.tool.handler({ startDate: '09/23/2026' });

  assert.equal(registration.tool.name, 'analyze_syslog');
  assert.equal(executeCount, 0);
  assert.notEqual(result.isError, true);
  assert.match(result.content[0].text, /end date/);
});

test('analyze_syslog rejects ranges over 2 weeks and bad dates without touching ServiceNow', async () => {
  const registration = registerTool();
  let executeCount = 0;
  registerAnalyzeSyslogTool(registration.server, async () => {
    executeCount += 1;
  }, { now: () => NOW });

  const tooLong = await registration.tool.handler({ startDate: '08/01/2026', endDate: '09/23/2026' });
  const badDate = await registration.tool.handler({ startDate: 'nope', endDate: '09/23/2026' });

  assert.equal(executeCount, 0);
  assert.equal(tooLong.isError, true);
  assert.match(tooLong.content[0].text, /2 weeks/);
  assert.equal(badDate.isError, true);
  assert.match(badDate.content[0].text, /Could not understand/);
});

test('analyze_syslog only reads the syslog table and reports findings', async () => {
  const registration = registerTool();
  const calls = [];
  const client = createReadOnlyClient(
    [
      [
        {
          sys_created_on: '2026-09-22 10:00:00',
          level: '2',
          source: 'MyScript',
          message: 'TypeError: x is not a function at line 42'
        },
        {
          sys_created_on: '2026-09-21 09:00:00',
          level: '2',
          source: 'MyScript',
          message: 'TypeError: x is not a function at line 57'
        },
        {
          sys_created_on: '2026-09-21 08:00:00',
          level: '1',
          source: 'REST',
          message: 'Request timed out after 30 seconds'
        }
      ]
    ],
    calls
  );

  let payload;
  registerAnalyzeSyslogTool(
    registration.server,
    async (operation) => {
      payload = await operation(client);
      return payload;
    },
    { now: () => NOW }
  );

  await registration.tool.handler({ startDate: 'Sept 20', endDate: '09/23' });

  // One query per day in the range.
  assert.equal(calls.length, 4);
  assert.ok(calls.every((call) => call.table === 'syslog'));
  assert.match(calls[0].query, /sys_created_on>=2026-09-20 00:00:00\^sys_created_on<=2026-09-20 23:59:59/);
  assert.match(calls[3].query, /sys_created_on>=2026-09-23 00:00:00\^sys_created_on<=2026-09-23 23:59:59/);
  assert.match(calls[0].query, /level=1\^ORlevel=2/);
  assert.deepEqual(payload.truncatedDays, []);
  assert.equal(payload.analysis.totalRecords, 3);
  assert.equal(payload.analysis.findings[0].count, 2);
  assert.match(payload.displayText, /Script errors/);
  assert.match(payload.displayText, /Performance/);
});

test('analyze_syslog caps each day separately so a noisy day cannot crowd out other days', async () => {
  const registration = registerTool();
  const calls = [];
  const fullPage = Array.from({ length: 500 }, (_, index) => ({
    sys_created_on: '2026-09-22 10:00:00',
    level: '2',
    source: 'src',
    message: `Failure ${index}`
  }));
  const quietDay = [{ sys_created_on: '2026-09-23 10:00:00', level: '1', source: 'src', message: 'quiet' }];
  // Day 1 returns full pages until its cap; day 2 returns a short page.
  const client = createReadOnlyClient([fullPage, fullPage, fullPage, quietDay], calls);

  let payload;
  registerAnalyzeSyslogTool(
    registration.server,
    async (operation) => {
      payload = await operation(client);
      return payload;
    },
    { now: () => NOW }
  );

  await registration.tool.handler({ startDate: '09/22/2026', endDate: '09/23/2026' });

  assert.deepEqual(
    calls.map((call) => [call.query.match(/sys_created_on>=(\S+)/)[1], call.offset]),
    [
      ['2026-09-22', 0],
      ['2026-09-22', 500],
      ['2026-09-22', 1000],
      ['2026-09-23', 0]
    ]
  );
  assert.deepEqual(payload.truncatedDays, ['2026-09-22']);
  assert.equal(payload.analysis.totalRecords, 1501);
  assert.match(payload.displayText, /Partial coverage on 1 day \(2026-09-22\)/);
});

test('analyze_syslog explains a 403 on the syslog table', async () => {
  const client = {
    async queryTableRecords() {
      throw new ServiceNowApiError('ServiceNow API request failed (403). User Not Authorized', 403);
    }
  };

  await assert.rejects(
    fetchSyslogRecords(client, { startDate: '2026-09-23', endDate: '2026-09-23' }),
    (error) => {
      assert.ok(error instanceof ServiceNowApiError);
      assert.equal(error.status, 403);
      assert.match(error.message, /read access to syslog/);
      assert.match(error.message, /Table API/);
      return true;
    }
  );
});

test('syslog is not a writable table for create_record or update_record', () => {
  assert.equal(ALLOWED_CRUD_TABLES.includes('syslog'), false);
});

test('normalizeMessage groups messages that differ only by ids and numbers', () => {
  assert.equal(
    normalizeMessage('Job 123 failed for abcdefabcdefabcdefabcdefabcdefab at 2026-09-22 10:00:00'),
    normalizeMessage('Job 456 failed for 0123456789abcdef0123456789abcdef at 2026-09-21 08:30:00')
  );
});

test('analyzeSyslogRecords flags volume spikes and ranks errors above warnings', () => {
  const range = { startDate: '2026-09-20', endDate: '2026-09-23' };
  const records = [
    ...Array.from({ length: 30 }, () => ({
      sys_created_on: '2026-09-22 10:00:00',
      level: '1',
      source: 'a',
      message: 'something odd'
    })),
    { sys_created_on: '2026-09-21 10:00:00', level: '2', source: 'b', message: 'Invalid password for user' }
  ];

  const analysis = analyzeSyslogRecords(records, range);

  assert.deepEqual(
    analysis.spikes.map((spike) => spike.date),
    ['2026-09-22']
  );
  assert.equal(analysis.findings[0].category, 'Security');
  assert.equal(analysis.findings[0].severity, 'high');
});

test('unwrapWrappedRecords merges ServletErrorListener copies and re-attributes unpaired ones', async () => {
  const { unwrapWrappedRecords } = await import('../src/tools/syslog-analysis.js');
  const wrapper = 'com.glide.ui.ServletErrorListener';
  const { records, duplicatesMerged } = unwrapWrappedRecords([
    { sys_created_on: '2026-09-22 10:00:00', level: '2', source: 'UADownloader-x', message: 'Download failed, status code = 403' },
    { sys_created_on: '2026-09-22 10:00:00', level: '2', source: wrapper, message: 'UADownloader-x: Download failed, status code = 403: no thrown error' },
    { sys_created_on: '2026-09-22 10:00:00', level: '2', source: wrapper, message: 'MyHandler: No solution found: no thrown error' },
    { sys_created_on: '2026-09-22 10:00:00', level: '2', source: wrapper, message: 'JavaScript evaluation error on:' }
  ]);

  assert.equal(duplicatesMerged, 1);
  assert.equal(records.length, 3);
  assert.deepEqual(
    records.map((record) => [record.source, record.message]),
    [
      ['UADownloader-x', 'Download failed, status code = 403'],
      ['MyHandler', 'No solution found'],
      [wrapper, 'JavaScript evaluation error on:']
    ]
  );
});

test('analyzeSyslogRecords collapses known configuration noise out of the problems table', () => {
  const range = { startDate: '2026-09-20', endDate: '2026-09-23' };
  const records = [
    ...Array.from({ length: 40 }, () => ({
      sys_created_on: '2026-09-22 10:00:00',
      level: '2',
      source: 'com.glide.ui.ServletErrorListener',
      message:
        'AlertStreamClassifierTextbaseHandler : No active solution is found for solution definition ml_x. To supress this error: no thrown error'
    })),
    { sys_created_on: '2026-09-22 11:00:00', level: '2', source: 'UADownloader-a', message: 'Request failed due to possible credential error, status code = 403' },
    { sys_created_on: '2026-09-22 12:00:00', level: '2', source: 'Real', message: 'TypeError: boom' }
  ];

  const analysis = analyzeSyslogRecords(records, range);

  assert.deepEqual(
    analysis.findings.map((finding) => finding.source),
    ['Real']
  );
  assert.deepEqual(
    analysis.lowPriority.map((entry) => [entry.id, entry.count]),
    [
      ['ml-not-configured', 40],
      ['usage-analytics-403', 1]
    ]
  );
});
