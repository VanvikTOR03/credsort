export type Tone = "green" | "orange" | "red" | "blue" | "accent" | undefined;
export const APP_STATUS: Record<string, { label: string; tone: Tone }> = {
  DRAFT: { label: "Draft", tone: undefined },
  PUBLISHED: { label: "Visible to lenders", tone: "blue" },
  OFFER_SELECTED: { label: "Offer chosen", tone: "accent" },
  FUNDED: { label: "Funded", tone: "green" },
  DISPUTED: { label: "In dispute", tone: "red" },
  CANCELLED: { label: "Cancelled", tone: "orange" },
  CLOSED: { label: "Closed", tone: undefined },
  WITHDRAWN: { label: "Withdrawn", tone: undefined },
};
export const OFFER_STATUS: Record<string, { label: string; tone: Tone }> = {
  SUBMITTED: { label: "Open", tone: "blue" }, SELECTED: { label: "Chosen", tone: "accent" }, FUNDED: { label: "Funded", tone: "green" },
  DISPUTED: { label: "In dispute", tone: "red" }, CANCELLED: { label: "Cancelled", tone: "orange" }, WITHDRAWN: { label: "Withdrawn", tone: undefined },
  REJECTED: { label: "Not chosen", tone: undefined }, EXPIRED: { label: "Expired", tone: undefined },
};
export const CHARGE_STATUS: Record<string, { label: string; tone: Tone; help: string }> = {
  PENDING: { label: "Waiting", tone: "blue", help: "Becomes payable 14 days after the lender confirms the payout." },
  PAYABLE: { label: "Payable", tone: "orange", help: "The dispute window has passed. You will receive an invoice." },
  HELD: { label: "On hold", tone: "red", help: "Paused while your dispute is reviewed." },
  CANCELLED: { label: "Cancelled", tone: undefined, help: "The loan was cancelled, so nothing is due." },
  WAIVED: { label: "Waived", tone: "green", help: "CredSort waived this fee." },
  PAID: { label: "Paid", tone: "green", help: "Thank you." },
  NO_FEE: { label: "No fee", tone: undefined, help: "No price was set when this offer was made, so nothing is due." },
};
export const CATEGORY: Record<string, { color: string; word: string }> = {
  A: { color: "var(--green)", word: "Strong" }, B: { color: "#7bc144", word: "Good" }, C: { color: "var(--orange)", word: "Fair" }, D: { color: "var(--red)", word: "Weak" },
};
export const REPAYMENT: Record<string, string> = { LINEAR: "Equal principal payments", ANNUITY: "Equal total payments", BULLET: "Everything at the end" };
export const FIELD_GROUPS: { title: string; fields: string[] }[] = [
  { title: "About the request", fields: ["requested_amount", "term_months", "purpose", "collateral"] },
  { title: "About your company", fields: ["industry", "employees_band", "company_name", "revenue_band", "revenue"] },
  { title: "Your assessment", fields: ["assessment_category", "assessment_score", "confidence_band"] },
  { title: "Your numbers", fields: ["revenue_growth", "ebitda_margin", "net_profit_margin", "current_ratio", "working_capital", "equity_ratio", "debt_to_ebitda", "dscr"] },
];
export const FIELD_PLAIN: Record<string, string> = {
  requested_amount: "How much you want to borrow", term_months: "How long you want to borrow", purpose: "What the money is for", collateral: "What you offer as security",
  industry: "Your industry", employees_band: "Roughly how many people work for you", company_name: "Your company name (otherwise lenders see no name)", revenue_band: "A range for your yearly revenue",
  revenue: "Your exact yearly revenue", assessment_category: "Your A to D category", assessment_score: "Your exact score out of 100", confidence_band: "How reliable your data is",
  revenue_growth: "How fast sales grow", ebitda_margin: "Operating profit as a share of sales", net_profit_margin: "Final profit as a share of sales", current_ratio: "Can you pay bills due within a year",
  working_capital: "Cash cushion for daily business", equity_ratio: "Share of the business funded by owners", debt_to_ebitda: "Years of operating profit to repay debt", dscr: "How comfortably income covers loan payments",
};
export const METRIC_GROUPS: { title: string; icon: string; color: string; codes: string[] }[] = [
  { title: "Profitability", icon: "trend", color: "green", codes: ["revenue", "revenue_growth", "ebitda_margin", "net_profit_margin"] },
  { title: "Liquidity", icon: "bolt", color: "blue", codes: ["current_ratio", "working_capital"] },
  { title: "Debt", icon: "gauge", color: "orange", codes: ["equity_ratio", "debt_to_ebitda", "dscr"] },
];
export function fmtMetric(code: string, unit: string, v: string | null) {
  if (v === null || v === undefined) return "n/a";
  const n = Number(v);
  if (unit === "CHF") return `CHF ${Math.round(n).toLocaleString("de-CH")}`;
  if (["revenue_growth", "ebitda_margin", "net_profit_margin", "equity_ratio"].includes(code)) return `${(n * 100).toFixed(1)}%`;
  return `${n.toFixed(2)}×`;
}
export const METRIC_HELP: Record<string, string> = {
  revenue: "Total sales in the period.", revenue_growth: "Sales compared with the year before.", ebitda_margin: "Operating profit before interest, tax and depreciation, as a share of sales.",
  net_profit_margin: "What is left after all costs and tax, as a share of sales.", current_ratio: "Short-term assets divided by short-term debts. Above 1 is healthy.",
  working_capital: "Short-term assets minus short-term debts.", equity_ratio: "Equity divided by total assets. Higher means less borrowed money.",
  debt_to_ebitda: "How many years of operating profit it would take to repay all debt. Lower is better.", dscr: "Income available for loan payments divided by the payments. Above 1.2 is comfortable.",
};
