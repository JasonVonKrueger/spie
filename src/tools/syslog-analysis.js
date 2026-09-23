import { eachDay } from './syslog-date-range.js';

const LEVEL_NAMES = { 0: 'Info', 1: 'Warning', 2: 'Error', 3: 'Debug' };

const MAX_PATTERNS = 15;
const MAX_SOURCES = 5;
const MAX_SAMPLE_LENGTH = 200;
const SPIKE_MIN_COUNT = 20;
const SPIKE_MEDIAN_MULTIPLIER = 2;

// ServletErrorListener re-logs many messages as "<source>: <message>: no thrown error", duplicating the
// record already logged under the real source. Those copies are merged (or re-attributed if unpaired).
const WRAPPER_SOURCES = new Set(['com.glide.ui.ServletErrorListener']);
const WRAPPED_MESSAGE = /^(\*\*\* Script|[\w.$-]+): ([\s\S]*)$/;

// Patterns that are usually configuration or platform-telemetry noise. They are collapsed into one line
// each instead of appearing in the problems table.
const LOW_PRIORITY_RULES = [
  {
    id: 'ml-not-configured',
    label: 'ML / Predictive Intelligence not active or unreachable',
    pattern:
      /no active solution is found for solution definition|ml_scheduler|sncmlscheduler|ApplicationsFingerprintUpdateUtil|ml_capability_definition/i,
    note: 'Harmless if you do not use these features. Otherwise activate the solution definitions and confirm outbound access to the ML scheduler service. The "No active solution" message itself explains how to suppress it.'
  },
  {
    id: 'usage-analytics-403',
    label: 'Usage analytics uploads/downloads refused (HTTP 403)',
    pattern: /UADownloader|USAGEANALYTICS/i,
    note: 'ServiceNow usage-analytics traffic is being refused, typically by blocked outbound access or entitlement. This is not a login or security attack.'
  }
];

// First matching rule wins, so order from most to least concerning.
const CATEGORY_RULES = [
  {
    category: 'Security',
    pattern:
      /(invalid|failed|incorrect).{0,40}(login|password|credential|authentication)|unauthorized|access denied|forbidden|security constraint|\bACL\b|permission denied/i,
    hint: 'Possible failed logins or access-control violations; check for brute-force attempts or misconfigured ACLs/integration users.'
  },
  {
    category: 'Database / resources',
    pattern:
      /out of memory|outofmemory|heap space|gc overhead|deadlock|lock wait|too many connections|connection pool|sqlexception|sql error|disk space/i,
    hint: 'Resource exhaustion or database contention; check node health, memory, and long-running transactions.'
  },
  {
    category: 'Performance',
    pattern: /timed? ?out|timeout|slow|long[- ]running|exceeded|took \d+|threshold|throttl|rate limit/i,
    hint: 'Slow or timed-out operations; look for expensive queries, business rules, or integrations.'
  },
  {
    category: 'Integration',
    pattern:
      /rest ?(api|message)|soap|mid server|connection (refused|reset)|unreachable|http (status )?[45]\d\d|endpoint|ldap|smtp|import set|transform map|unknown host/i,
    hint: 'Failing outbound/inbound integration; check credentials, endpoints, MID Server status, and the remote system.'
  },
  {
    category: 'Scheduler / events',
    pattern: /scheduled job|scheduler|sys_trigger|event queue|skipped|stuck/i,
    hint: 'Scheduled jobs or event processing may be delayed or failing; check the Scheduled Jobs and Event Log.'
  },
  {
    category: 'Script errors',
    pattern:
      /typeerror|referenceerror|syntaxerror|evaluator|script include|business rule|javascript|is not a function|null ?pointer|undefined|exception/i,
    hint: 'Server-side script failures; review the referenced script, and recent customizations or update sets.'
  }
];

function matchLowPriority(message, source) {
  const text = `${source ?? ''} ${message ?? ''}`;
  return LOW_PRIORITY_RULES.find((rule) => rule.pattern.test(text)) ?? null;
}

function cleanWrappedMessage(text) {
  return text.replace(/[:\s]*(?:no thrown error)?[:\s]*$/i, '').trim();
}

function sameMessage(a, b) {
  return a.length > 0 && b.length > 0 && (a.startsWith(b) || b.startsWith(a));
}

const minuteOf = (record) => `${record.level}|${(record.sys_created_on || '').slice(0, 16)}|${record.source}`;

export function unwrapWrappedRecords(records) {
  const direct = new Map();

  for (const record of records) {
    if (!WRAPPER_SOURCES.has(record.source)) {
      const key = minuteOf(record);
      direct.set(key, [...(direct.get(key) ?? []), String(record.message ?? '').trim()]);
    }
  }

  const kept = [];
  let duplicatesMerged = 0;

  for (const record of records) {
    const match = WRAPPER_SOURCES.has(record.source) ? String(record.message ?? '').match(WRAPPED_MESSAGE) : null;

    if (!match) {
      kept.push(record);
      continue;
    }

    const unwrapped = { ...record, source: match[1], message: cleanWrappedMessage(match[2]) };
    const candidates = direct.get(minuteOf(unwrapped));
    const index = candidates?.findIndex((candidate) => sameMessage(candidate, unwrapped.message)) ?? -1;

    if (index >= 0) {
      candidates.splice(index, 1);
      duplicatesMerged += 1;
    } else {
      kept.push(unwrapped);
    }
  }

  return { records: kept, duplicatesMerged };
}

function categorize(message, source) {
  const text = `${source ?? ''} ${message ?? ''}`;
  const rule = CATEGORY_RULES.find((candidate) => candidate.pattern.test(text));
  return rule ?? { category: 'Other', hint: 'Review the sample message and source for context.' };
}

// Collapses ids, timestamps and numbers so repeated occurrences of the same problem group together.
export function normalizeMessage(message) {
  return String(message ?? '')
    .split('\n')[0]
    .replace(/[0-9a-f]{32}/gi, '<sys_id>')
    .replace(/\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?/g, '<time>')
    .replace(/\b0x[0-9a-f]+\b/gi, '<hex>')
    .replace(/\b\d+(?:\.\d+)?\b/g, '<n>')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, MAX_SAMPLE_LENGTH);
}

function severityOf({ level, count, category }) {
  const isError = level === 2;

  if (isError && (count >= 25 || category === 'Security' || category === 'Database / resources')) {
    return 'high';
  }

  if (isError || count >= 25) {
    return 'medium';
  }

  return 'low';
}

const SEVERITY_RANK = { high: 0, medium: 1, low: 2 };

function median(values) {
  if (values.length === 0) {
    return 0;
  }

  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

/**
 * Looks for potential platform problems in warning/error syslog records.
 * `records` need `sys_created_on`, `level`, `source` and `message`.
 */
export function analyzeSyslogRecords(rawRecords, range) {
  const { records, duplicatesMerged } = unwrapWrappedRecords(rawRecords);
  const levelCounts = { Error: 0, Warning: 0, Other: 0 };
  const sourceCounts = new Map();
  const patterns = new Map();
  const dailyCounts = new Map(eachDay(range.startDate, range.endDate).map((day) => [day, 0]));

  for (const record of records) {
    const level = Number(record.level);
    const source = record.source || '(no source)';
    const createdOn = record.sys_created_on || '';
    const day = createdOn.slice(0, 10);

    levelCounts[level === 2 ? 'Error' : level === 1 ? 'Warning' : 'Other'] += 1;

    if (dailyCounts.has(day)) {
      dailyCounts.set(day, dailyCounts.get(day) + 1);
    }

    if (level === 2) {
      sourceCounts.set(source, (sourceCounts.get(source) ?? 0) + 1);
    }

    const normalized = normalizeMessage(record.message);
    const key = `${level}|${source}|${normalized}`;
    const existing = patterns.get(key);

    if (existing) {
      existing.count += 1;
      if (createdOn && createdOn < existing.firstSeen) existing.firstSeen = createdOn;
      if (createdOn && createdOn > existing.lastSeen) existing.lastSeen = createdOn;
    } else {
      const lowPriority = matchLowPriority(record.message, source);
      const { category, hint } = categorize(record.message, source);
      patterns.set(key, {
        lowPriority,
        level,
        levelName: LEVEL_NAMES[level] ?? String(record.level),
        source,
        category,
        hint,
        count: 1,
        firstSeen: createdOn,
        lastSeen: createdOn,
        sampleMessage: String(record.message ?? '').split('\n')[0].slice(0, MAX_SAMPLE_LENGTH)
      });
    }
  }

  const allPatterns = [...patterns.values()];

  const lowPriority = LOW_PRIORITY_RULES.map((rule) => {
    const matched = allPatterns.filter((pattern) => pattern.lowPriority === rule);
    return {
      id: rule.id,
      label: rule.label,
      note: rule.note,
      patterns: matched.length,
      count: matched.reduce((total, pattern) => total + pattern.count, 0)
    };
  })
    .filter((entry) => entry.count > 0)
    .sort((a, b) => b.count - a.count);

  const findings = allPatterns
    .filter((pattern) => !pattern.lowPriority)
    .map(({ lowPriority: _ignored, ...pattern }) => ({ ...pattern, severity: severityOf(pattern) }))
    .sort(
      (a, b) =>
        SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity] || b.count - a.count || b.level - a.level
    );

  const days = [...dailyCounts.entries()].map(([date, count]) => ({ date, count }));
  const dailyMedian = median(days.map((day) => day.count));
  const spikes = days.filter(
    (day) => day.count >= SPIKE_MIN_COUNT && day.count >= dailyMedian * SPIKE_MEDIAN_MULTIPLIER
  );

  const topErrorSources = [...sourceCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, MAX_SOURCES)
    .map(([source, count]) => ({ source, count }));

  return {
    totalRecords: records.length,
    levelCounts,
    duplicatesMerged,
    distinctPatterns: allPatterns.length,
    hiddenPatterns: Math.max(0, findings.length - MAX_PATTERNS),
    findings: findings.slice(0, MAX_PATTERNS),
    lowPriority,
    topErrorSources,
    dailyCounts: days,
    spikes
  };
}

function cell(value) {
  return String(value ?? '')
    .replace(/\|/g, '\\|')
    .replace(/\s+/g, ' ')
    .trim();
}

export function formatSyslogAnalysis(analysis, range, { truncatedDays = [], maxRecordsPerDay }) {
  const lines = [
    `# Syslog analysis: ${range.startDate} to ${range.endDate} (${range.days} day${range.days === 1 ? '' : 's'}, UTC)`,
    '',
    `Analyzed ${analysis.totalRecords} unique warning/error records: ${analysis.levelCounts.Error} errors, ${analysis.levelCounts.Warning} warnings, in ${analysis.distinctPatterns} distinct patterns.${
      analysis.duplicatesMerged > 0
        ? ` ${analysis.duplicatesMerged} duplicate copies logged by ServletErrorListener were merged.`
        : ''
    }`
  ];

  if (truncatedDays.length > 0) {
    lines.push(
      '',
      `> **Partial coverage on ${truncatedDays.length} day${truncatedDays.length === 1 ? '' : 's'} (${truncatedDays.join(', ')}).** Only the newest ${maxRecordsPerDay} warning/error records of each of those days were analyzed, so their earliest hours are missing and their counts are minimums. Other days were analyzed in full.`
    );
  }

  if (analysis.totalRecords === 0) {
    lines.push('', 'No warning or error records were found in this range.');
    return lines.join('\n');
  }

  lines.push('', '## Potential problems', '');
  if (analysis.findings.length === 0) {
    lines.push('None beyond the low-priority items below.');
  } else {
    lines.push('| Severity | Category | Level | Count | Source | First seen | Last seen | Sample message |');
    lines.push('| --- | --- | --- | --- | --- | --- | --- | --- |');
    for (const finding of analysis.findings) {
      lines.push(
        `| ${finding.severity} | ${finding.category} | ${finding.levelName} | ${finding.count} | ${cell(finding.source)} | ${finding.firstSeen} | ${finding.lastSeen} | ${cell(finding.sampleMessage)} |`
      );
    }
    if (analysis.hiddenPatterns > 0) {
      lines.push('', `_${analysis.hiddenPatterns} lower-ranked patterns are not shown._`);
    }
  }

  if (analysis.lowPriority.length > 0) {
    lines.push('', '## Likely configuration or telemetry noise (low priority)', '');
    for (const entry of analysis.lowPriority) {
      lines.push(
        `- **${entry.label}:** ${entry.count} records in ${entry.patterns} pattern${entry.patterns === 1 ? '' : 's'}. ${entry.note}`
      );
    }
  }

  const hints = [...new Map(analysis.findings.map((f) => [f.category, f.hint])).entries()];
  if (hints.length > 0) {
    lines.push('', '## What to check', '');
    for (const [category, hint] of hints) {
      lines.push(`- **${category}:** ${hint}`);
    }
  }

  if (analysis.spikes.length > 0) {
    lines.push('', '## Volume spikes', '');
    for (const spike of analysis.spikes) {
      lines.push(`- ${spike.date}: ${spike.count} warning/error records`);
    }
  }

  if (analysis.topErrorSources.length > 0) {
    lines.push('', '## Sources with the most errors', '');
    for (const { source, count } of analysis.topErrorSources) {
      lines.push(`- ${cell(source)}: ${count}`);
    }
  }

  lines.push(
    '',
    '_Only warning and error records were analyzed, and categories are keyword-based heuristics, so treat findings as leads to investigate rather than confirmed faults._'
  );

  return lines.join('\n');
}
