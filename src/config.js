import fs from 'node:fs';
import path from 'node:path';
import { parse } from 'dotenv';

import { ConfigError } from './errors.js';

export const SUPPORTED_GRANT_TYPES = [
  'client_credentials',
  'password',
  'authorization_code',
  'refresh_token'
];

const BASE_REQUIRED_VARIABLES = [
  'SERVICENOW_INSTANCE_URL',
  'SERVICENOW_CLIENT_ID',
  'SERVICENOW_CLIENT_SECRET',
  'SERVICENOW_OAUTH_GRANT_TYPE'
];

export const GRANT_TYPE_REQUIREMENTS = {
  client_credentials: [],
  password: ['SERVICENOW_USERNAME', 'SERVICENOW_PASSWORD'],
  authorization_code: ['SERVICENOW_AUTHORIZATION_CODE', 'SERVICENOW_REDIRECT_URI'],
  refresh_token: ['SERVICENOW_REFRESH_TOKEN']
};

function readEnvFile(envPath) {
  if (!fs.existsSync(envPath)) {
    throw new ConfigError(
      `Missing .env file at ${envPath}. Copy .env.example to .env and set the required ServiceNow variables.`,
      ['.env']
    );
  }

  return parse(fs.readFileSync(envPath, 'utf8'));
}

function getTrimmedValue(source, key) {
  const value = source[key];
  return typeof value === 'string' ? value.trim() : '';
}

function normalizeInstanceUrl(instanceUrl) {
  try {
    const url = new URL(instanceUrl);
    url.pathname = '';
    url.search = '';
    url.hash = '';
    return url.toString().replace(/\/$/, '');
  } catch {
    throw new ConfigError(
      'SERVICENOW_INSTANCE_URL must be a valid absolute URL, for example https://example.service-now.com.',
      ['SERVICENOW_INSTANCE_URL']
    );
  }
}

export function loadServiceNowConfig(options = {}) {
  const envPath = options.envPath ?? path.resolve(process.cwd(), '.env');
  const envFileValues = readEnvFile(envPath);
  const source = { ...process.env, ...envFileValues };

  const grantType = getTrimmedValue(source, 'SERVICENOW_OAUTH_GRANT_TYPE').toLowerCase();

  if (!grantType) {
    throw new ConfigError(
      'ServiceNow configuration is incomplete. Set SERVICENOW_OAUTH_GRANT_TYPE in .env.',
      ['SERVICENOW_OAUTH_GRANT_TYPE']
    );
  }

  if (!SUPPORTED_GRANT_TYPES.includes(grantType)) {
    throw new ConfigError(
      `Unsupported SERVICENOW_OAUTH_GRANT_TYPE "${grantType}". Supported values: ${SUPPORTED_GRANT_TYPES.join(', ')}.`,
      ['SERVICENOW_OAUTH_GRANT_TYPE']
    );
  }

  const requiredVariables = [
    ...BASE_REQUIRED_VARIABLES,
    ...GRANT_TYPE_REQUIREMENTS[grantType]
  ];
  const missingVariables = requiredVariables.filter((key) => !getTrimmedValue(source, key));

  if (missingVariables.length > 0) {
    throw new ConfigError(
      `ServiceNow configuration is incomplete. Add the following variable(s) to .env: ${missingVariables.join(', ')}.`,
      missingVariables
    );
  }

  return {
    envPath,
    instanceUrl: normalizeInstanceUrl(getTrimmedValue(source, 'SERVICENOW_INSTANCE_URL')),
    clientId: getTrimmedValue(source, 'SERVICENOW_CLIENT_ID'),
    clientSecret: getTrimmedValue(source, 'SERVICENOW_CLIENT_SECRET'),
    grantType,
    username: getTrimmedValue(source, 'SERVICENOW_USERNAME') || undefined,
    password: getTrimmedValue(source, 'SERVICENOW_PASSWORD') || undefined,
    authorizationCode: getTrimmedValue(source, 'SERVICENOW_AUTHORIZATION_CODE') || undefined,
    redirectUri: getTrimmedValue(source, 'SERVICENOW_REDIRECT_URI') || undefined,
    refreshToken: getTrimmedValue(source, 'SERVICENOW_REFRESH_TOKEN') || undefined
  };
}
