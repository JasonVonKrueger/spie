import { AuthError, ServiceNowApiError } from './errors.js';

function getResponseMessage(body, status) {
  if (body && typeof body === 'object') {
    const message =
      body.error?.message ||
      body.error_description ||
      body.error?.detail ||
      body.message ||
      body.status;

    if (typeof message === 'string' && message.trim()) {
      return message.trim();
    }
  }

  if (typeof body === 'string' && body.trim()) {
    return body.trim();
  }

  return `ServiceNow request failed with status ${status}.`;
}

async function parseResponseBody(response) {
  const contentType = response.headers.get('content-type') || '';

  if (contentType.includes('application/json')) {
    return response.json();
  }

  return response.text();
}

export class ServiceNowClient {
  constructor(config, authClient, fetchImpl = fetch) {
    this.config = config;
    this.authClient = authClient;
    this.fetchImpl = fetchImpl;
  }

  async testConnection() {
    try {
      await this.request('GET', '/api/now/table/sys_user', {
        searchParams: {
          sysparm_limit: '1',
          sysparm_fields: 'sys_id'
        }
      });
    } catch (error) {
      if (error instanceof ServiceNowApiError && error.status === 403) {
        throw new ServiceNowApiError(
          'Connected to ServiceNow, but the OAuth principal cannot read the validation endpoint (/api/now/table/sys_user). Grant read access to that table or adjust the integration user permissions.',
          403,
          error.details
        );
      }

      throw error;
    }
  }

  async queryTableRecords({ table, query, fields, limit = 10, offset = 0 }) {
    const response = await this.request('GET', `/api/now/table/${encodeURIComponent(table)}`, {
      searchParams: {
        ...(query ? { sysparm_query: query } : {}),
        ...(fields?.length ? { sysparm_fields: fields.join(',') } : {}),
        sysparm_limit: String(limit),
        sysparm_offset: String(offset)
      }
    });

    return response.result ?? response;
  }

  async getRecordBySysId({ table, sysId, fields }) {
    const response = await this.request(
      'GET',
      `/api/now/table/${encodeURIComponent(table)}/${encodeURIComponent(sysId)}`,
      {
        searchParams: {
          ...(fields?.length ? { sysparm_fields: fields.join(',') } : {})
        }
      }
    );

    return response.result ?? response;
  }

  async createTableRecord({ table, fields }) {
    const response = await this.request('POST', `/api/now/table/${encodeURIComponent(table)}`, {
      body: fields
    });

    return response.result ?? response;
  }

  async updateTableRecord({ table, sysId, fields }) {
    const response = await this.request(
      'PATCH',
      `/api/now/table/${encodeURIComponent(table)}/${encodeURIComponent(sysId)}`,
      {
        body: fields
      }
    );

    return response.result ?? response;
  }

  async request(method, path, options = {}) {
    const accessToken = await this.authClient.getAccessToken();
    const url = new URL(path, this.config.instanceUrl);

    if (options.searchParams) {
      for (const [key, value] of Object.entries(options.searchParams)) {
        if (value !== undefined && value !== null && value !== '') {
          url.searchParams.set(key, value);
        }
      }
    }

    let response;
    try {
      response = await this.fetchImpl(url, {
        method,
        headers: {
          Accept: 'application/json',
          Authorization: ['Bearer', accessToken].join(' '),
          ...(options.body ? { 'Content-Type': 'application/json' } : {})
        },
        ...(options.body ? { body: JSON.stringify(options.body) } : {})
      });
    } catch (error) {
      throw new ServiceNowApiError(`Unable to reach ServiceNow at ${url.origin}. ${error.message}`, 0);
    }

    const responseBody = await parseResponseBody(response);

    if (response.status === 401) {
      throw new AuthError(getResponseMessage(responseBody, response.status), {
        status: response.status
      });
    }

    if (!response.ok) {
      throw new ServiceNowApiError(
        `ServiceNow API request failed (${response.status}). ${getResponseMessage(
          responseBody,
          response.status
        )}`,
        response.status,
        responseBody
      );
    }

    return responseBody;
  }
}
