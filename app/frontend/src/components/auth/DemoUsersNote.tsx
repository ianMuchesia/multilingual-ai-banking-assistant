import { Info } from "lucide-react";
import { demoUsers } from "../../config";

/** Seeded development users. Demo environment only: never ship real credentials like this. */
export function DemoUsersNote({ onPick }: { onPick: (username: string, password: string) => void }) {
  return (
    <aside className="demo-note" aria-labelledby="demo-note-title">
      <p id="demo-note-title" className="demo-note__title label">
        <Info size={14} aria-hidden="true" /> Demo environment
      </p>
      <p className="demo-note__text">
        Sign in as one of the seeded customers. Password for all: <code className="mono">password123</code>
      </p>
      <ul className="demo-note__users">
        {demoUsers.map((u) => (
          <li key={u.username}>
            <button type="button" className="chip" onClick={() => onPick(u.username, u.password)}>
              <span className="mono">{u.username}</span>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
