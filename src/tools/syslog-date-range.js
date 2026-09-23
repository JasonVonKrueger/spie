export const MAX_SYSLOG_RANGE_DAYS = 14;

const DAY_MS = 24 * 60 * 60 * 1000;

const MONTHS = [
  'january',
  'february',
  'march',
  'april',
  'may',
  'june',
  'july',
  'august',
  'september',
  'october',
  'november',
  'december'
];

export class DateInputError extends Error {
  constructor(message) {
    super(message);
    this.name = 'DateInputError';
  }
}

function monthFromName(word) {
  if (word === 'sept') {
    return 9;
  }

  if (word.length < 3) {
    return null;
  }

  const index = MONTHS.findIndex((month) => month === word || (word.length === 3 && month.startsWith(word)));
  return index === -1 ? null : index + 1;
}

function toCalendarDate(year, month, day, input) {
  const utc = new Date(Date.UTC(year, month - 1, day));

  if (utc.getUTCFullYear() !== year || utc.getUTCMonth() !== month - 1 || utc.getUTCDate() !== day) {
    throw new DateInputError(`"${input}" is not a real calendar date.`);
  }

  return { year, month, day };
}

/**
 * Parses a date typed in natural language into a calendar date. When no year is given, the year of
 * `now` is used. Numeric dates are read US-style (month first).
 *
 * Supported: 09/23/2026, 9/23, 9-23-2026, 2026-09-23, Sept 23, 2026, September 23rd,
 * 23 Sep 2026, today, yesterday.
 */
export function parseDateInput(input, now = new Date()) {
  const text = String(input ?? '')
    .trim()
    .toLowerCase()
    .replace(/,/g, ' ')
    .replace(/(\d)(?:st|nd|rd|th)\b/g, '$1')
    .replace(/\s+/g, ' ');

  const currentYear = now.getFullYear();
  let match;

  if (text === 'today' || text === 'yesterday') {
    const date = new Date(now.getFullYear(), now.getMonth(), now.getDate() - (text === 'yesterday' ? 1 : 0));
    return { year: date.getFullYear(), month: date.getMonth() + 1, day: date.getDate() };
  }

  if ((match = text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/))) {
    return toCalendarDate(Number(match[1]), Number(match[2]), Number(match[3]), input);
  }

  if ((match = text.match(/^(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{4}))?$/))) {
    return toCalendarDate(match[3] ? Number(match[3]) : currentYear, Number(match[1]), Number(match[2]), input);
  }

  if ((match = text.match(/^([a-z]+)\.? (\d{1,2})(?: (\d{4}))?$/))) {
    const month = monthFromName(match[1]);
    if (month) {
      return toCalendarDate(match[3] ? Number(match[3]) : currentYear, month, Number(match[2]), input);
    }
  }

  if ((match = text.match(/^(\d{1,2}) ([a-z]+)\.?(?: (\d{4}))?$/))) {
    const month = monthFromName(match[2]);
    if (month) {
      return toCalendarDate(match[3] ? Number(match[3]) : currentYear, month, Number(match[1]), input);
    }
  }

  throw new DateInputError(
    `Could not understand the date "${input}". Try a format like "09/23/2026", "Sept 23, 2026", or "Sept 23" (the current year is assumed when no year is given).`
  );
}

function pad(value) {
  return String(value).padStart(2, '0');
}

function formatDate({ year, month, day }) {
  return `${year}-${pad(month)}-${pad(day)}`;
}

/**
 * Resolves the two typed dates into an inclusive UTC range and enforces the 2-week limit.
 * The range covers 00:00:00 on the start date through 23:59:59 on the end date.
 */
export function resolveSyslogDateRange(startInput, endInput, now = new Date()) {
  const start = parseDateInput(startInput, now);
  const end = parseDateInput(endInput, now);

  const startMs = Date.UTC(start.year, start.month - 1, start.day);
  const endMs = Date.UTC(end.year, end.month - 1, end.day);

  if (endMs < startMs) {
    throw new DateInputError(
      `The end date (${formatDate(end)}) is before the start date (${formatDate(start)}). Please provide the earlier date first.`
    );
  }

  const days = Math.round((endMs - startMs) / DAY_MS) + 1;

  if (days > MAX_SYSLOG_RANGE_DAYS) {
    throw new DateInputError(
      `The range ${formatDate(start)} to ${formatDate(end)} spans ${days} days. At most ${MAX_SYSLOG_RANGE_DAYS} days (2 weeks) of syslog records can be analyzed at a time. Please choose a shorter range.`
    );
  }

  return {
    startDate: formatDate(start),
    endDate: formatDate(end),
    startDateTime: `${formatDate(start)} 00:00:00`,
    endDateTime: `${formatDate(end)} 23:59:59`,
    days
  };
}
