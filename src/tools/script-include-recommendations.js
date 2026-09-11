const SCRIPT_INCLUDE_TABLE = 'sys_script_include';
const SCRIPT_INCLUDE_FIELDS = ['sys_id', 'name', 'api_name', 'script'];
const MAX_SCRIPT_INCLUDE_MATCHES = 100;
const MIN_FUNCTION_NAME_SCORE = 85;
const FUNCTION_NAME_STOP_WORDS = new Set(['function', 'initialize']);

function getTextValue(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function unique(values) {
  return [...new Set(values)];
}

function normalizeFunctionToken(token) {
  const normalized = token.toLowerCase();

  if (['log', 'logs', 'logged', 'logging', 'logger'].includes(normalized)) {
    return 'log';
  }

  if (['message', 'messages', 'msg'].includes(normalized)) {
    return 'message';
  }

  return normalized.endsWith('ss') ? normalized : normalized.replace(/s$/, '');
}

function tokenizeFunctionName(functionName) {
  return unique(
    getTextValue(functionName)
      .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
      .split(/[^A-Za-z0-9_$]+/)
      .flatMap((token) => token.split(/(?=[A-Z])/))
      .map(normalizeFunctionToken)
      .filter((token) => token.length > 2 && !FUNCTION_NAME_STOP_WORDS.has(token))
  );
}

function normalizeFunctionName(functionName) {
  return tokenizeFunctionName(functionName).join('');
}

export function extractFunctionNames(script) {
  const functionNames = [];
  const patterns = [
    /\bfunction\s+([A-Za-z_$][\w$]*)\s*\(/g,
    /\b([A-Za-z_$][\w$]*)\s*:\s*function\s*\(/g,
    /\bthis\.([A-Za-z_$][\w$]*)\s*=\s*function\s*\(/g,
    /\b([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*{/g
  ];

  for (const pattern of patterns) {
    for (const match of getTextValue(script).matchAll(pattern)) {
      functionNames.push(match[1]);
    }
  }

  return unique(functionNames).filter((name) => tokenizeFunctionName(name).length > 0);
}

function getRequestedFunctionNames(fields, requestedFunctionNames = []) {
  return unique([...requestedFunctionNames, ...extractFunctionNames(fields.script)]).filter(Boolean);
}

function toSnakeCaseFunctionName(functionName) {
  return getTextValue(functionName)
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .replace(/[^A-Za-z0-9_$]+/g, '_')
    .toLowerCase();
}

function buildEncodedQuery(requestedFunctionNames) {
  const searchTerms = unique([
    ...requestedFunctionNames.map(getTextValue),
    ...requestedFunctionNames.map((name) => getTextValue(name).toLowerCase()),
    ...requestedFunctionNames.map(toSnakeCaseFunctionName),
    ...requestedFunctionNames.map(normalizeFunctionName)
  ]).filter(Boolean);

  return searchTerms.map((term) => `scriptLIKE${term}`).join('^OR');
}

function getEditDistance(leftValue, rightValue) {
  const left = getTextValue(leftValue);
  const right = getTextValue(rightValue);
  const distances = Array.from({ length: left.length + 1 }, () => Array(right.length + 1).fill(0));

  for (let index = 0; index <= left.length; index += 1) {
    distances[index][0] = index;
  }

  for (let index = 0; index <= right.length; index += 1) {
    distances[0][index] = index;
  }

  for (let leftIndex = 1; leftIndex <= left.length; leftIndex += 1) {
    for (let rightIndex = 1; rightIndex <= right.length; rightIndex += 1) {
      const substitutionCost = left[leftIndex - 1] === right[rightIndex - 1] ? 0 : 1;

      distances[leftIndex][rightIndex] = Math.min(
        distances[leftIndex - 1][rightIndex] + 1,
        distances[leftIndex][rightIndex - 1] + 1,
        distances[leftIndex - 1][rightIndex - 1] + substitutionCost
      );
    }
  }

  return distances[left.length][right.length];
}

function getSimilarity(leftValue, rightValue) {
  const left = getTextValue(leftValue);
  const right = getTextValue(rightValue);
  const maxLength = Math.max(left.length, right.length);

  if (maxLength === 0) {
    return 0;
  }

  return (maxLength - getEditDistance(left, right)) / maxLength;
}

function scoreFunctionName(requestedFunctionName, candidateFunctionName) {
  if (requestedFunctionName.toLowerCase() === candidateFunctionName.toLowerCase()) {
    return {
      score: 100,
      matchedTerms: ['exact function name']
    };
  }

  const normalizedRequestedFunctionName = normalizeFunctionName(requestedFunctionName);
  const normalizedCandidateFunctionName = normalizeFunctionName(candidateFunctionName);

  if (normalizedRequestedFunctionName === normalizedCandidateFunctionName) {
    return {
      score: 95,
      matchedTerms: ['normalized function name']
    };
  }

  const similarity = getSimilarity(normalizedRequestedFunctionName, normalizedCandidateFunctionName);

  return {
    score: Math.round(similarity * 100),
    matchedTerms: similarity >= 0.85 ? [`whole-name similarity ${Math.round(similarity * 100)}%`] : []
  };
}

function buildScriptIncludeLink(client, sysId) {
  if (!client.config?.instanceUrl || !sysId) {
    return null;
  }

  return `${client.config.instanceUrl}/sys_script_include.do?sys_id=${encodeURIComponent(sysId)}`;
}

function escapeMarkdownTableCell(value) {
  return getTextValue(value).replace(/\|/g, '\\|') || '-';
}

function buildMarkdownTable(matches) {
  const rows = matches.map((match) => [
    escapeMarkdownTableCell(match.scriptIncludeName),
    escapeMarkdownTableCell(match.apiName),
    escapeMarkdownTableCell(match.functionName),
    match.link ? `[Open](${match.link})` : '-'
  ]);

  return [
    '| Script Include | API Name | Possible Duplicate Function | Link |',
    '| --- | --- | --- | --- |',
    ...rows.map((row) => `| ${row.join(' | ')} |`)
  ].join('\n');
}

export async function findSimilarScriptIncludeFunctions(client, fields, options = {}) {
  const requestedFunctionNames = getRequestedFunctionNames(fields, options.requestedFunctionNames);
  const excludedSysIds = new Set(options.excludeSysIds ?? []);

  if (requestedFunctionNames.length === 0) {
    return null;
  }

  const candidates = await client.queryTableRecords({
    table: SCRIPT_INCLUDE_TABLE,
    query: buildEncodedQuery(requestedFunctionNames),
    fields: SCRIPT_INCLUDE_FIELDS,
    limit: MAX_SCRIPT_INCLUDE_MATCHES
  });
  const records = Array.isArray(candidates) ? candidates : [candidates].filter(Boolean);
  const matches = records
    .filter((record) => !excludedSysIds.has(record.sys_id))
    .flatMap((record) =>
      extractFunctionNames(record.script).flatMap((functionName) =>
        requestedFunctionNames.map((requestedFunctionName) => {
          const score = scoreFunctionName(requestedFunctionName, functionName);

          return {
            sysId: record.sys_id,
            scriptIncludeName: record.name,
            apiName: record.api_name,
            functionName,
            requestedFunctionName,
            link: buildScriptIncludeLink(client, record.sys_id),
            ...score
          };
        })
      )
    )
    .filter((match) => match.score >= MIN_FUNCTION_NAME_SCORE)
    .sort((left, right) => right.score - left.score);

  if (matches.length === 0) {
    return null;
  }

  return {
    message: 'Possible duplicate Script Include functions were found by function name. ServiceNow was not modified.',
    displayText: [
      'Possible duplicate Script Include functions were found by function name. ServiceNow was not modified.',
      '',
      buildMarkdownTable(matches)
    ].join('\n'),
    requestedFunctionNames,
    markdownTable: buildMarkdownTable(matches),
    matches
  };
}