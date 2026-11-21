import { useEffect, useState } from "react";
import { Layers, RefreshCw } from "lucide-react";
import { rpc } from "./bridge";
import "./anki-review.css";

const columns = [
  ["new", "새 카드"],
  ["learning", "학습 중"],
  ["review", "복습"],
] as const;
type Counts = Record<(typeof columns)[number][0], number>;
type Deck = Counts & { id: number; name: string };
type Review = { decks: Deck[]; totals: Counts };
const number = new Intl.NumberFormat("ko-KR");

export function AnkiReview() {
  const [attempt, setAttempt] = useState(0);
  const [review, setReview] = useState<Review | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      void rpc<Review>("anki.read")
        .then((value) => {
          if (active) setReview(value);
        })
        .catch((reason: unknown) => {
          if (!active) return;
          setReview(null);
          setError(reason instanceof Error ? reason.message : "Anki 데이터를 가져오지 못했습니다.");
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 0);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [attempt]);

  return (
    <section className="glass anki-review" aria-labelledby="anki-review-heading">
      <div className="anki-review-header">
        <h2 id="anki-review-heading"><Layers size={18} aria-hidden="true" /> Anki</h2>
        <button type="button" disabled={loading} onClick={() => {
          setLoading(true);
          setError("");
          setAttempt((value) => value + 1);
        }}>
          <RefreshCw size={15} aria-hidden="true" /> {loading ? "불러오는 중" : "새로고침"}
        </button>
      </div>
      {error && <p className="muted" role="status">{error}</p>}
      {review && (
        <>
          <dl className="anki-review-totals">
            {columns.map(([key, label]) => (
              <div key={key}><dt>{label}</dt><dd>{number.format(review.totals[key])}</dd></div>
            ))}
          </dl>
          {review.decks.length ? (
            <details className="anki-review-decks">
              <summary>덱별 현황 <small>{number.format(review.decks.length)}개</small></summary>
              <table aria-label="Anki 덱별 현황">
                <thead>
                  <tr><th scope="col">덱</th>{columns.map(([key, label]) => <th key={key} scope="col">{label}</th>)}</tr>
                </thead>
                <tbody>
                  {review.decks.map((deck) => (
                    <tr key={deck.id}>
                      <th scope="row">{deck.name.replaceAll("::", " / ")}</th>
                      {columns.map(([key]) => <td key={key}>{number.format(deck[key])}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          ) : <p className="muted">집계할 덱 없음</p>}
        </>
      )}
    </section>
  );
}
