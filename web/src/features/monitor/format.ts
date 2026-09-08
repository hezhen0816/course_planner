/** 監控頁共用的時間格式：一律帶日期，避免跨日的日誌與最後檢查時間看起來像今天。 */
export function formatDateTime(value: string | number | Date | null | undefined): string {
  if (value === null || value === undefined || value === '') return '---';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '---';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(date.getMonth() + 1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}
