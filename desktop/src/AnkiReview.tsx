import { t, useLanguage } from "./i18n";
import { useEffect, useState } from "react";
import { Layers, RefreshCw } from "lucide-react";
import { invalidateMenuReads, peekMenuRead, readMenu } from "./menuReads";
import { ChangedNumber } from "./ChangedNumber";
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
  useLanguage();
  const [attempt, setAttempt] = useState(0);
  const [review, setReview] = useState<Review | null>(() => peekMenuRead("anki.read") ?? null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(() => !review);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      void readMenu<Review>("anki.read")
        .then((value) => {
          if (active) setReview(value);
        })
        .catch((reason: unknown) => {
          if (!active) return;
          setError(reason instanceof Error ? reason.message : t("Anki 데이터를 가져오지 못했습니다."));
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
          invalidateMenuReads("anki.read");
          setLoading(true);
          setError("");
          setAttempt((value) => value + 1);
        }}>
          <RefreshCw size={15} aria-hidden="true" /> {loading ? t("불러오는 중") : t("새로고침")}
        </button>
      </div>
      {error && <p className="muted" role="status">{error}</p>}
      {review && (
        <>
          <dl className="anki-review-totals">
            {columns.map(([key, label]) => (
              <div key={key}><dt>{t(label)}</dt><dd><ChangedNumber value={number.format(review.totals[key])} /></dd></div>
            ))}
          </dl>
          {review.decks.length ? (
            <details className="anki-review-decks">
              <summary>{t("덱별 현황")}{" "}<small>{number.format(review.decks.length)}{t("개")}</small></summary>
              <table aria-label={t("Anki 덱별 현황")}>
                <thead>
                  <tr><th scope="col">{t("덱")}</th>{columns.map(([key, label]) => <th key={key} scope="col">{t(label)}</th>)}</tr>
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
          ) : <p className="muted">{t("집계할 덱 없음")}</p>}
        </>
      )}
    </section>
  );
}
