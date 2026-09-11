export function toSuccessResult(payload) {
  if (payload?.isError) {
    return {
      isError: true,
      content: [
        {
          type: 'text',
          text: payload.displayText ?? JSON.stringify(payload, null, 2)
        }
      ],
      structuredContent: payload
    };
  }

  return {
    content: [
      {
        type: 'text',
        text: payload?.displayText ?? payload?.similarFunctions?.markdownTable ?? JSON.stringify(payload, null, 2)
      }
    ],
    structuredContent: payload
  };
}