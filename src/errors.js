export class ConfigError extends Error {
  constructor(message, missingVariables = []) {
    super(message);
    this.name = 'ConfigError';
    this.missingVariables = missingVariables;
  }
}

export class AuthError extends Error {
  constructor(message, options = {}) {
    super(message);
    this.name = 'AuthError';
    this.status = options.status;
  }
}

export class ServiceNowApiError extends Error {
  constructor(message, status, details) {
    super(message);
    this.name = 'ServiceNowApiError';
    this.status = status;
    this.details = details;
  }
}

export function toToolErrorResult(error) {
  if (error instanceof ConfigError) {
    return {
      isError: true,
      content: [{ type: 'text', text: error.message }]
    };
  }

  if (error instanceof AuthError) {
    return {
      isError: true,
      content: [{ type: 'text', text: `ServiceNow authentication failed. ${error.message}` }]
    };
  }

  if (error instanceof ServiceNowApiError) {
    return {
      isError: true,
      content: [{ type: 'text', text: error.message }]
    };
  }

  return {
    isError: true,
    content: [{ type: 'text', text: 'Unexpected ServiceNow MCP server error.' }]
  };
}
