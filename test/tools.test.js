import assert from 'node:assert/strict';
import test from 'node:test';

import { ALLOWED_CRUD_TABLES } from '../src/tools/allowed-crud-tables.js';
import { registerCreateRecordTool } from '../src/tools/create-record.js';
import { registerUpdateRecordTool } from '../src/tools/update-record.js';

function registerTool() {
  let tool;

  const server = {
    tool(name, description, schema, handler) {
      tool = { name, description, schema, handler };
    }
  };

  return {
    server,
    get tool() {
      return tool;
    }
  };
}

test('create_record rejects tables outside the allowlist', async () => {
  const registration = registerTool();
  let executeCount = 0;

  registerCreateRecordTool(registration.server, async () => {
    executeCount += 1;
    return { content: [] };
  });

  const result = await registration.tool.handler({
    table: 'sys_user',
    fields: { name: 'Test User' }
  });

  assert.equal(registration.tool.name, 'create_record');
  assert.equal(executeCount, 0);
  assert.equal(result.isError, true);
  assert.match(result.content[0].text, /sys_user/);

  for (const table of ALLOWED_CRUD_TABLES) {
    assert.match(result.content[0].text, new RegExp(table));
  }
});

test('update_record rejects tables outside the allowlist', async () => {
  const registration = registerTool();
  let executeCount = 0;

  registerUpdateRecordTool(registration.server, async () => {
    executeCount += 1;
    return { content: [] };
  });

  const result = await registration.tool.handler({
    table: 'sys_user',
    sysId: 'user123',
    fields: { name: 'Test User' }
  });

  assert.equal(registration.tool.name, 'update_record');
  assert.equal(executeCount, 0);
  assert.equal(result.isError, true);
  assert.match(result.content[0].text, /sys_user/);

  for (const table of ALLOWED_CRUD_TABLES) {
    assert.match(result.content[0].text, new RegExp(table));
  }
});

test('update_record updates records in allowed tables', async () => {
  const registration = registerTool();
  let operationResult;

  registerUpdateRecordTool(registration.server, async (operation) => {
    operationResult = await operation({
      async updateTableRecord(request) {
        return { updated: true, ...request };
      }
    });

    return { structuredContent: operationResult };
  });

  const result = await registration.tool.handler({
    table: 'incident',
    sysId: 'incident123',
    fields: { short_description: 'Updated incident' }
  });

  assert.deepEqual(operationResult, {
    table: 'incident',
    sysId: 'incident123',
    result: {
      updated: true,
      table: 'incident',
      sysId: 'incident123',
      fields: { short_description: 'Updated incident' }
    }
  });
  assert.deepEqual(result, { structuredContent: operationResult });
});

test('update_record blocks script include updates when another script include has a similar function name', async () => {
  const registration = registerTool();
  let updateCount = 0;

  registerUpdateRecordTool(registration.server, async (operation) => {
    const operationResult = await operation({
      config: { instanceUrl: 'https://example.service-now.com' },
      async queryTableRecords(request) {
        assert.equal(request.table, 'sys_script_include');
        assert.match(request.query, /scriptLIKEsubtractNumbers/);

        return [
          {
            sys_id: 'mathutils123',
            name: 'MathUtils',
            api_name: 'global.MathUtils',
            script: 'MathUtils.prototype = { subtractNumbers: function(num1, num2) {} };'
          },
          {
            sys_id: 'bobs123',
            name: 'Bobs_update_set',
            api_name: 'global.Bobs_update_set',
            script: 'Bobs_update_set.prototype = { subtractNumbers: function(a, b) {} };'
          }
        ];
      },
      async updateTableRecord() {
        updateCount += 1;
      }
    });

    return { structuredContent: operationResult };
  });

  const result = await registration.tool.handler({
    table: 'sys_script_include',
    sysId: 'mathutils123',
    fields: {
      script: 'MathUtils.prototype = { subtractNumbers: function(num1, num2) {} };'
    }
  });

  assert.equal(updateCount, 0);
  assert.equal(result.structuredContent.isError, true);
  assert.match(result.structuredContent.displayText, /ServiceNow was not modified/);
  assert.deepEqual(result.structuredContent.similarFunctions.matches.map((match) => [match.sysId, match.functionName]), [
    ['bobs123', 'subtractNumbers']
  ]);
  assert.match(result.structuredContent.similarFunctions.markdownTable, /Bobs_update_set/);
  assert.match(result.structuredContent.similarFunctions.markdownTable, /subtractNumbers/);
});

test('update_record does not update a script include even when confirmation is passed', async () => {
  const registration = registerTool();
  let updateCount = 0;

  registerUpdateRecordTool(registration.server, async (operation) => {
    const operationResult = await operation({
      config: { instanceUrl: 'https://example.service-now.com' },
      async queryTableRecords() {
        return [
          {
            sys_id: 'bobs123',
            name: 'Bobs_update_set',
            api_name: 'global.Bobs_update_set',
            script: 'Bobs_update_set.prototype = { subtractNumbers: function(a, b) {} };'
          }
        ];
      },
      async updateTableRecord() {
        updateCount += 1;
      }
    });

    return { structuredContent: operationResult };
  });

  const fields = {
    script: 'MathUtils.prototype = { subtractNumbers: function(num1, num2) {} };'
  };
  const result = await registration.tool.handler({
    table: 'sys_script_include',
    sysId: 'mathutils123',
    fields,
    confirmSimilarFunctionUpdate: true
  });

  assert.equal(updateCount, 0);
  assert.equal(result.structuredContent.isError, true);
  assert.deepEqual(result.structuredContent.similarFunctions.matches.map((match) => [match.sysId, match.functionName]), [
    ['bobs123', 'subtractNumbers']
  ]);
});

test('create_record creates records in allowed tables', async () => {
  const registration = registerTool();
  let operationResult;

  registerCreateRecordTool(registration.server, async (operation) => {
    operationResult = await operation({
      async createTableRecord(request) {
        return { sys_id: 'abc123', ...request };
      }
    });

    return { structuredContent: operationResult };
  });

  const result = await registration.tool.handler({
    table: 'incident',
    fields: { short_description: 'Test incident' }
  });

  assert.deepEqual(operationResult, {
    table: 'incident',
    result: {
      sys_id: 'abc123',
      table: 'incident',
      fields: { short_description: 'Test incident' }
    }
  });
  assert.deepEqual(result, { structuredContent: operationResult });
});

test('create_record lists existing script include functions with similar names', async () => {
  const registration = registerTool();
  let createCount = 0;

  registerCreateRecordTool(registration.server, async (operation) => {
    const operationResult = await operation({
      config: { instanceUrl: 'https://example.service-now.com' },
      async queryTableRecords(request) {
        assert.equal(request.table, 'sys_script_include');

        return [
          {
            sys_id: 'existing123',
            name: 'IncidentUtils',
            api_name: 'global.IncidentUtils',
            description: 'Utilities for incident priority calculation',
            script: 'var IncidentUtils = Class.create(); IncidentUtils.prototype = { calculatePriority: function() {} };'
          },
          {
            sys_id: 'existing456',
            name: 'PriorityLogger',
            api_name: 'global.PriorityLogger',
            description: 'Log incident priority calculations',
            script: 'var PriorityLogger = Class.create(); PriorityLogger.prototype = { calculatePriority: function() {} };'
          }
        ];
      },
      async createTableRecord() {
        createCount += 1;
      }
    });

    return { structuredContent: operationResult };
  });

  const result = await registration.tool.handler({
    table: 'sys_script_include',
    fields: {
      name: 'Incident priority helper',
      description: 'Calculate incident priority',
      script: 'function calculatePriority() {}'
    }
  });

  assert.equal(createCount, 0);
  assert.equal(result.structuredContent.isError, true);
  assert.equal(result.structuredContent.table, 'sys_script_include');
  assert.match(result.structuredContent.similarFunctions.message, /Possible duplicate Script Include functions/);
  assert.match(result.structuredContent.displayText, /ServiceNow was not modified/);
  assert.match(result.structuredContent.similarFunctions.markdownTable, /\| Script Include \| API Name \| Possible Duplicate Function \| Link \|/);
  assert.deepEqual(
    result.structuredContent.similarFunctions.matches.map((match) => [match.sysId, match.functionName]),
    [
      ['existing123', 'calculatePriority'],
      ['existing456', 'calculatePriority']
    ]
  );
  assert.deepEqual(result.structuredContent.similarFunctions.matches[0], {
    sysId: 'existing123',
    scriptIncludeName: 'IncidentUtils',
    apiName: 'global.IncidentUtils',
    functionName: 'calculatePriority',
    requestedFunctionName: 'calculatePriority',
    link: 'https://example.service-now.com/sys_script_include.do?sys_id=existing123',
    score: 100,
    matchedTerms: ['exact function name']
  });
});

test('create_record ignores script include functions with different whole names', async () => {
  const registration = registerTool();
  let createCount = 0;

  registerCreateRecordTool(registration.server, async (operation) => {
    const operationResult = await operation({
      config: { instanceUrl: 'https://example.service-now.com' },
      async queryTableRecords(request) {
        assert.equal(request.table, 'sys_script_include');
        assert.match(request.query, /scriptLIKElogMessage/);

        return [
          {
            sys_id: 'bobs123',
            name: 'Bobs_update_set',
            api_name: 'global.Bobs_update_set',
            description: '',
            script: [
              'var Bobs_update_set = Class.create();',
              'Bobs_update_set.prototype = {',
              '  logger: function(msg) {',
              '    gs.info(msg);',
              '  },',
              "  type: 'Bobs_update_set'",
              '};'
            ].join('\n')
          }
        ];
      },
      async createTableRecord() {
        createCount += 1;
      }
    });

    return { structuredContent: operationResult };
  });

  const result = await registration.tool.handler({
    table: 'sys_script_include',
    fields: {
      name: 'MyScript',
      description: 'Provides a function to log messages passed into it.',
      script: [
        'var MyScript = Class.create();',
        'MyScript.prototype = {',
        '  logMessage: function(message) {',
        '    gs.info(message);',
        '  }',
        '};'
      ].join('\n')
    }
  });

  assert.equal(createCount, 1);
  assert.equal(result.structuredContent.similarFunctions, undefined);
});

test('create_record searches exact requested function names so existing addNumbers functions are found', async () => {
  const registration = registerTool();
  let createCount = 0;

  registerCreateRecordTool(registration.server, async (operation) => {
    const operationResult = await operation({
      config: { instanceUrl: 'https://example.service-now.com' },
      async queryTableRecords(request) {
        assert.equal(request.table, 'sys_script_include');
        assert.equal(request.limit, 100);
        assert.match(request.query, /scriptLIKEaddNumbers/);

        return [
          {
            sys_id: 'bobs123',
            name: 'Bobs_update_set',
            api_name: 'global.Bobs_update_set',
            script: [
              'var Bobs_update_set = Class.create();',
              'Bobs_update_set.prototype = {',
              '  addNumbers: function (a, b) {',
              '    return parseInt(a) + parseInt(b);',
              '  },',
              "  type: 'Bobs_update_set'",
              '};'
            ].join('\n')
          }
        ];
      },
      async createTableRecord() {
        createCount += 1;
      }
    });

    return { structuredContent: operationResult };
  });

  const result = await registration.tool.handler({
    table: 'sys_script_include',
    fields: {
      name: 'MathUtils',
      description: 'Utility script include with math helper functions.',
      script: [
        'var MathUtils = Class.create();',
        'MathUtils.prototype = {',
        '  addNumbers: function(num1, num2) {',
        '    return num1 + num2;',
        '  },',
        "  type: 'MathUtils'",
        '};'
      ].join('\n')
    }
  });

  assert.equal(createCount, 0);
  assert.deepEqual(result.structuredContent.similarFunctions.matches[0], {
    sysId: 'bobs123',
    scriptIncludeName: 'Bobs_update_set',
    apiName: 'global.Bobs_update_set',
    functionName: 'addNumbers',
    requestedFunctionName: 'addNumbers',
    link: 'https://example.service-now.com/sys_script_include.do?sys_id=bobs123',
    score: 100,
    matchedTerms: ['exact function name']
  });
  assert.match(result.structuredContent.similarFunctions.markdownTable, /Bobs_update_set/);
  assert.match(result.structuredContent.similarFunctions.markdownTable, /addNumbers/);
});

test('create_record ignores script include functions that only share loose name pieces', async () => {
  const registration = registerTool();
  let createRequest;

  registerCreateRecordTool(registration.server, async (operation) => {
    const operationResult = await operation({
      config: { instanceUrl: 'https://example.service-now.com' },
      async queryTableRecords(request) {
        assert.equal(request.table, 'sys_script_include');
        assert.doesNotMatch(request.query, /scriptLIKEadd\^/);
        assert.doesNotMatch(request.query, /scriptLIKEnumber/);

        return [
          {
            sys_id: 'collection123',
            name: 'CollectionItem',
            api_name: 'global.CollectionItem',
            script: 'CollectionItem.prototype = { addFileToCollections: function(file) {} };'
          },
          {
            sys_id: 'asset123',
            name: 'AssetNumberAbbreviation',
            api_name: 'global.AssetNumberAbbreviation',
            script: 'AssetNumberAbbreviation.prototype = { getNumberAbbreviated: function(value) {} };'
          }
        ];
      },
      async createTableRecord(request) {
        createRequest = request;
        return { sys_id: 'new123' };
      }
    });

    return { structuredContent: operationResult };
  });

  const fields = {
    name: 'MathUtils',
    script: 'MathUtils.prototype = { addNumbers: function(num1, num2) {} };'
  };
  const result = await registration.tool.handler({
    table: 'sys_script_include',
    fields
  });

  assert.deepEqual(createRequest, {
    table: 'sys_script_include',
    fields
  });
  assert.equal(result.structuredContent.similarFunctions, undefined);
});

test('create_record does not create a script include even when confirmation is passed', async () => {
  const registration = registerTool();
  let createCount = 0;

  registerCreateRecordTool(registration.server, async (operation) => {
    const operationResult = await operation({
      config: { instanceUrl: 'https://example.service-now.com' },
      async queryTableRecords() {
        return [
          {
            sys_id: 'bobs123',
            name: 'Bobs_update_set',
            api_name: 'global.Bobs_update_set',
            script: 'Bobs_update_set.prototype = { logMessage: function(msg) {} };'
          }
        ];
      },
      async createTableRecord() {
        createCount += 1;
      }
    });

    return { structuredContent: operationResult };
  });

  const fields = {
    name: 'MyScript',
    script: 'MyScript.prototype = { logMessage: function(message) {} };'
  };
  const result = await registration.tool.handler({
    table: 'sys_script_include',
    fields,
    confirmSimilarFunctionCreation: true
  });

  assert.equal(createCount, 0);
  assert.equal(result.structuredContent.isError, true);
  assert.deepEqual(result.structuredContent.similarFunctions.matches.map((match) => [match.sysId, match.functionName]), [
    ['bobs123', 'logMessage']
  ]);
});

test('create_record creates a script include when no similar function names appear to match', async () => {
  const registration = registerTool();
  let createRequest;

  registerCreateRecordTool(registration.server, async (operation) => {
    const operationResult = await operation({
      config: { instanceUrl: 'https://example.service-now.com' },
      async queryTableRecords() {
        return [];
      },
      async createTableRecord(request) {
        createRequest = request;
        return { sys_id: 'new123' };
      }
    });

    return { structuredContent: operationResult };
  });

  const fields = {
    name: 'UniqueIntegrationUtils',
    description: 'Handle a unique integration calculation',
    script: 'function calculateUniqueIntegrationValue() {}'
  };
  const result = await registration.tool.handler({
    table: 'sys_script_include',
    fields
  });

  assert.deepEqual(createRequest, {
    table: 'sys_script_include',
    fields
  });
  assert.deepEqual(result.structuredContent, {
    table: 'sys_script_include',
    result: { sys_id: 'new123' }
  });
});