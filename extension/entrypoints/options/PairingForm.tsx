import { useState } from "react";
import type { InstanceInfo, PairResponse } from "@/lib/api/messages";

/**
 * Pairing-code entry. On submit it sends `{ type: "PAIR", pairingCode }` to the
 * background worker via `chrome.runtime.sendMessage` — it NEVER fetches the
 * backend directly (locked decision). The worker mints + stores the token on
 * success; on `{ ok: true }` we surface the instance name/version and notify the
 * parent (so the health badge re-checks). On `{ ok: false }` we show the error.
 */

export interface PairingFormProps {
  /** Called after a successful pair so the parent can refresh health. */
  readonly onPaired: () => void;
}

export function PairingForm({ onPaired }: PairingFormProps) {
  const [code, setCode] = useState<string>("");
  const [pending, setPending] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [instance, setInstance] = useState<InstanceInfo | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setPending(true);
    setError(null);
    setInstance(null);
    try {
      const res = (await chrome.runtime.sendMessage({
        type: "PAIR",
        pairingCode: code,
      })) as PairResponse;
      if (res.ok) {
        setInstance(res.instance ?? null);
        setCode("");
        onPaired();
      } else {
        setError(res.error ?? "Pairing failed. Check the code and try again.");
      }
    } catch {
      setError("Could not reach the extension worker. Try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <label htmlFor="pairing-code" style={{ fontSize: 13, fontWeight: 600 }}>
        Pairing code
      </label>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          id="pairing-code"
          name="pairing-code"
          inputMode="numeric"
          autoComplete="off"
          maxLength={6}
          value={code}
          onChange={(event) => setCode(event.target.value.trim())}
          placeholder="123456"
          style={{ fontSize: 14, padding: "6px 8px", width: 120, letterSpacing: 2 }}
        />
        <button
          type="submit"
          disabled={pending || code.length === 0}
          style={{ fontSize: 14, padding: "6px 12px" }}
        >
          {pending ? "Pairing…" : "Pair"}
        </button>
      </div>
      <p style={{ fontSize: 12, color: "#666", margin: 0 }}>
        Run <code>kestrel extension pair</code> in your Kestrel terminal to get the current code.
      </p>
      {instance && (
        <p role="status" style={{ fontSize: 13, color: "#0f5132", margin: 0 }}>
          Paired with {instance.name} v{instance.version}.
        </p>
      )}
      {error && (
        <p role="alert" style={{ fontSize: 13, color: "#842029", margin: 0 }}>
          {error}
        </p>
      )}
    </form>
  );
}
