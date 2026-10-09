import type { ConfirmResponse } from "../../types/api";
import { ReceiptCard } from "../replies/ReceiptCard";

interface Props {
  titleId: string;
  result: ConfirmResponse;
  onDone: () => void;
}

export function SuccessState({ titleId, result, onDone }: Props) {
  return (
    <div className="success">
      <svg className="success__check" viewBox="0 0 52 52" aria-hidden="true">
        <circle className="success__circle" cx="26" cy="26" r="24" fill="none" />
        <path className="success__tick" fill="none" d="M15 27l7 7 15-16" />
      </svg>
      <h2 id={titleId} className="sheet__title">
        Done. Money on its way.
      </h2>
      <ReceiptCard receipt={result.receipt} />
      <button type="button" className="btn btn--primary btn--block" onClick={onDone} autoFocus>
        Done
      </button>
    </div>
  );
}
