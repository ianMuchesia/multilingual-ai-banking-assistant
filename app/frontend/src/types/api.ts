// Types mirroring the backend API contract exactly.

export interface User {
  id: number;
  username: string;
  full_name: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
}

export type AccountType = "savings" | "current";

export interface Account {
  id: number;
  number: string;
  type: AccountType;
  currency: "KES";
  balance: number;
}

export interface Me extends User {
  accounts: Account[];
}

export type Direction = "in" | "out";

export interface Transaction {
  id: number;
  reference: string;
  account_id: number;
  direction: Direction;
  amount: number;
  channel: string;
  counterparty: string;
  description: string;
  created_at: string;
  balance_after: number;
}

export interface Receipt {
  reference: string;
  amount: number;
  channel: string;
  counterparty: string;
  from_account: string;
  created_at: string;
  status: string;
}

// ---- chat ----

export type Route = "direct" | "confirm" | "reject" | "llm";

/** [intent, score] */
export type IntentScore = [string, number];
/** [text, intent, score] */
export type NearestExample = [string, string, number];

export interface Decision {
  intent: string;
  route: Route;
  score: number;
  margin: number;
  top3: IntentScore[];
  nearest_examples: NearestExample[];
  reasons: string[];
  latency_ms: number;
}

export interface BalanceData {
  accounts: Account[];
}
export interface MiniStatementData {
  transactions: Transaction[];
}
export interface FullStatementData {
  start: string;
  end: string;
  transactions: Transaction[];
}
export interface FindTransactionData {
  matches: Transaction[];
}
export interface ViewReceiptData {
  receipt: Receipt | null;
  candidates: Transaction[];
}
export interface TransferHelpData {
  topic: string;
  answer: string;
}

interface ReplyBase<K extends string, D> {
  kind: K;
  text: string;
  data: D;
}

export type Reply =
  | ReplyBase<"balance", BalanceData>
  | ReplyBase<"mini_statement", MiniStatementData>
  | ReplyBase<"full_statement", FullStatementData>
  | ReplyBase<"find_transaction", FindTransactionData>
  | ReplyBase<"view_receipt", ViewReceiptData>
  | ReplyBase<"transfer_help", TransferHelpData>
  | ReplyBase<"confirm", null>
  | ReplyBase<"reject", null>
  | ReplyBase<"llm_pending", null>;

export type ReplyKind = Reply["kind"];

// ---- actions / slots ----

export type ActionIntent = "internal_transfer" | "external_transfer" | "lipa_na_mpesa";

export interface InternalTransferSlots {
  from_account?: string | null;
  to_account?: string | null;
  amount?: number | null;
}

export interface ExternalTransferSlots {
  from_account?: string | null;
  destination_type?: "bank" | "mobile" | null;
  /** Bank name, e.g. "KCB"; required when destination_type is "bank". */
  bank?: string | null;
  destination?: string | null;
  amount?: number | null;
}

export interface LipaNaMpesaSlots {
  from_account?: string | null;
  payment_type?: "till" | "paybill" | null;
  till_or_paybill?: string | null;
  account_number?: string | null;
  amount?: number | null;
}

/** Slot values as exchanged with the backend. */
export type SlotValue = string | number | null;
export type Slots = Record<string, SlotValue | undefined>;

export interface PendingAction {
  id: string;
  intent: string;
  slots: Slots;
  missing_slots: string[];
  expires_at: string;
}

export interface ChatRequest {
  message: string;
}

export interface ChatResponse {
  decision: Decision;
  reply: Reply;
  pending_action: PendingAction | null;
}

export interface ConfirmRequest {
  slots: Slots;
}

export interface ConfirmResponse {
  status: "executed";
  transaction: Transaction;
  receipt: Receipt;
}

export interface CancelResponse {
  status: "cancelled";
}

export type RouterMode = "gemma" | "stub";

export interface HealthResponse {
  status: string;
  router_mode: RouterMode;
}

export interface ErrorBody {
  detail?: string | { msg?: string }[];
}
