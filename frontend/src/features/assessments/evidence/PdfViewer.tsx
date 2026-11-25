import {
  getDocument,
  GlobalWorkerOptions,
  OPS,
  Util,
  type PDFDocumentProxy,
  type PDFPageProxy,
} from "pdfjs-dist";
import type { RenderTask, TextItem } from "pdfjs-dist/types/src/display/api";
import type { PageViewport } from "pdfjs-dist/types/src/display/display_utils";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { useEffect, useMemo, useRef, useState } from "react";

GlobalWorkerOptions.workerSrc = workerUrl;

/** Where to look: the evidence pages and the quoted text to highlight on them. */
export type PdfTarget = { page: number; pageEnd?: number; quote?: string; nonce: number };

type Hit = { page: number; items: TextItem[] } | null;
type Match = { status: "found" | "notFound" | "noText"; page: number } | null;

const PAGE_GAP = 12; // .pdf-page margin-bottom

/**
 * Scroll only the PDF pane. scrollIntoView also scrolls every scrollable ancestor (the whole
 * page), which made the report column beside the PDF jump on each evidence click.
 */
function scrollInsidePane(el: HTMLElement, align: "start" | "center") {
  const pane = el.closest<HTMLElement>(".pdf-scroll");
  if (!pane) return;
  const offset = el.getBoundingClientRect().top - pane.getBoundingClientRect().top;
  const shift = align === "center" ? (pane.clientHeight - el.offsetHeight) / 2 : 8;
  pane.scrollTop += offset - shift;
}

const normalize = (s: string) => s.normalize("NFC").toLowerCase().replace(/\s+/g, "");

/**
 * Text items on one page covering the quote. Spacing and line breaks differ between the
 * backend parser and pdf.js, so both sides drop whitespace before comparing. Long quotes
 * fall back to their beginning; the highlight then still spans the quote's length.
 */
function findQuotes(items: TextItem[], quote: string): number[][] {
  const wanted = normalize(quote);
  if (!wanted) return [];
  let joined = "";
  const owner: number[] = [];
  items.forEach((item, i) => {
    const text = normalize(item.str);
    joined += text;
    for (let k = 0; k < text.length; k++) owner.push(i);
  });
  // Every occurrence: a page may draw the same text more than once (see visibleOccurrence).
  for (const probe of [wanted, ...[80, 40, 20].filter((n) => wanted.length > n).map((n) => wanted.slice(0, n))]) {
    const found: number[][] = [];
    for (let at = joined.indexOf(probe); at >= 0; at = joined.indexOf(probe, at + 1)) {
      found.push([...new Set(owner.slice(at, at + wanted.length))].sort((a, b) => a - b));
    }
    if (found.length) return found;
  }
  return [];
}

type Band = { y0: number; y1: number };

/** Vertical page range each top-level frame (form XObject) actually shows, in PDF units. */
async function frameBands(page: PDFPageProxy): Promise<Band[]> {
  const ops = await page.getOperatorList();
  const bands: Band[] = [];
  let depth = 0;
  ops.fnArray.forEach((fn, i) => {
    if (fn === OPS.paintFormXObjectBegin) {
      depth += 1;
      const [matrix, bbox] = ops.argsArray[i] as [number[] | null, number[] | null];
      if (depth === 1 && bbox) {
        const [, , , d = 1, , f = 0] = matrix ?? [1, 0, 0, 1, 0, 0];
        const ys = [bbox[1]!, bbox[3]!].map((y) => d * y + f);
        bands.push({ y0: Math.min(...ys), y1: Math.max(...ys) });
      }
    } else if (fn === OPS.paintFormXObjectEnd) {
      depth -= 1;
    }
  });
  return bands;
}

/** Items repeat with this period when every frame draws a full copy of the page's text. */
function copyPeriod(items: TextItem[], copies: number): number | null {
  const n = items.length;
  const guess = Math.round(n / copies);
  for (let p = Math.max(1, guess - 12); p <= Math.min(n - 1, guess + 12); p++) {
    let same = 0;
    let checked = 0;
    for (let i = 0; i < Math.min(40, n - p); i++) {
      if (!items[i]!.str.trim()) continue;
      checked += 1;
      if (items[i]!.str === items[i + p]!.str) same += 1;
    }
    if (checked >= 5 && same / checked >= 0.8) return p;
  }
  return null;
}

/**
 * Pick the occurrence a reader can see. Some dataset PDFs split a page into frames that each
 * draw the whole page shifted, clipped to their own band (the backend parser de-duplicates
 * the same thing); pdf.js returns every copy, and the first one may be hidden, which put the
 * highlight a few lines off. An occurrence is visible when it falls inside its frame's band.
 */
async function visibleOccurrence(page: PDFPageProxy, items: TextItem[], found: number[][]) {
  if (found.length < 2) return found[0];
  const bands = await frameBands(page);
  const period = bands.length > 1 ? copyPeriod(items, bands.length) : null;
  if (!period) return found[0];
  return (
    found.find((indices) => {
      const first = indices[0]!;
      const band = bands[Math.floor(first / period)];
      const y = items[first]!.transform[5] as number;
      return !band || (y >= band.y0 - 1 && y <= band.y1 + 1);
    }) ?? found[0]
  );
}

/** Renders the PDF itself (not the browser viewer) so evidence can be highlighted in place. */
export function PdfViewer({
  url,
  target,
  onPage,
}: {
  url: string;
  target: PdfTarget | null;
  onPage?: (page: number) => void;
}) {
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aspect, setAspect] = useState(1.414);
  const [width, setWidth] = useState(0);
  const [hit, setHit] = useState<Hit>(null);
  const [match, setMatch] = useState<Match>(null);
  const [view, setView] = useState({ top: 0, height: 0 });
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Results of a load that was already torn down (StrictMode runs effects twice in dev)
    // must not overwrite the live one: its promise rejects with "Worker was destroyed".
    let cancelled = false;
    setError(null);
    const task = getDocument({ url });
    task.promise.then(
      async (loaded) => {
        const first = (await loaded.getPage(1)).getViewport({ scale: 1 });
        if (cancelled) return;
        setAspect(first.height / first.width);
        setDoc(loaded);
      },
      (e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      },
    );
    return () => {
      cancelled = true;
      setDoc(null);
      void task.destroy();
    };
  }, [url]);

  // The scroll box only exists once the document has loaded, so measure it from then on.
  useEffect(() => {
    const box = scroller.current;
    if (!box) return;
    const measure = () => {
      setWidth(Math.max(0, Math.floor(box.clientWidth - 24)));
      setView({ top: box.scrollTop, height: box.clientHeight });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(box);
    return () => observer.disconnect();
  }, [doc]);

  // Find the quote on the evidence pages, then bring that page into view.
  useEffect(() => {
    if (!doc || !target) return;
    let cancelled = false;
    (async () => {
      const last = Math.min(target.pageEnd ?? target.page, doc.numPages);
      let found: Hit = null;
      let anyText = false;
      for (let p = target.page; p <= last && !found; p++) {
        const page = await doc.getPage(p);
        const content = await page.getTextContent();
        const items = content.items.filter((i): i is TextItem => "str" in i);
        if (items.some((i) => i.str.trim())) anyText = true;
        const occurrences = target.quote ? findQuotes(items, target.quote) : [];
        const chosen = await visibleOccurrence(page, items, occurrences);
        if (chosen?.length) found = { page: p, items: chosen.map((i) => items[i]!) };
      }
      if (cancelled) return;
      setHit(found);
      setMatch({
        status: found ? "found" : anyText ? "notFound" : "noText",
        page: found?.page ?? target.page,
      });
      const page = found?.page ?? target.page;
      onPage?.(page);
      const el = document.getElementById(`pdf-page-${page}`);
      if (el) scrollInsidePane(el, "start");
    })();
    return () => {
      cancelled = true;
    };
  }, [doc, target, onPage]);

  if (error) return <p className="pdf-message">Không mở được tệp PDF: {error}</p>;
  if (!doc) return <p className="pdf-message">Đang mở hợp đồng…</p>;
  return (
    <div className="pdf-viewer">
      {match && (
        <p className={`pdf-match ${match.status}`}>
          {match.status === "found"
            ? `Đoạn được tô vàng ở trang ${match.page}.`
            : match.status === "noText"
              ? `Trang ${match.page} là bản scan (ảnh), không tô sáng được; hãy tìm đoạn này trên trang.`
              : `Không dò được đúng đoạn trên trang ${match.page}; đang hiển thị trang đó.`}
        </p>
      )}
      <div
        className="pdf-scroll"
        ref={scroller}
        onScroll={(e) =>
          setView({ top: e.currentTarget.scrollTop, height: e.currentTarget.clientHeight })
        }
      >
        {width > 0 &&
          Array.from({ length: doc.numPages }, (_, i) => i + 1).map((n) => {
            // Pages share the first page's size until drawn; draw only those near the view
            // (about one screen above and below), so a 40-page contract stays light.
            const slot = width * aspect + PAGE_GAP;
            const top = (n - 1) * slot;
            const near = top + slot > view.top - view.height && top < view.top + 2 * view.height;
            return (
              <PdfPage
                key={n}
                doc={doc}
                number={n}
                width={width}
                aspect={aspect}
                near={near}
                highlight={hit?.page === n ? hit.items : null}
                nonce={target?.nonce}
              />
            );
          })}
      </div>
    </div>
  );
}

function PdfPage({
  doc,
  number,
  width,
  aspect,
  near,
  highlight,
  nonce,
}: {
  doc: PDFDocumentProxy;
  number: number;
  width: number;
  aspect: number;
  near: boolean;
  highlight: TextItem[] | null;
  nonce?: number;
}) {
  const box = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [visible, setVisible] = useState(false);
  const [viewport, setViewport] = useState<PageViewport | null>(null);
  useEffect(() => {
    if (near) setVisible(true); // once drawn, a page stays drawn
  }, [near]);

  const shouldRender = visible || !!highlight;
  useEffect(() => {
    if (!shouldRender || !canvas.current) return;
    let cancelled = false;
    let task: RenderTask | null = null;
    (async () => {
      const page = await doc.getPage(number);
      const base = page.getViewport({ scale: 1 });
      const next = page.getViewport({ scale: width / base.width });
      const ratio = window.devicePixelRatio || 1;
      const el = canvas.current;
      if (cancelled || !el) return;
      el.width = Math.floor(next.width * ratio);
      el.height = Math.floor(next.height * ratio);
      el.style.width = `${next.width}px`;
      el.style.height = `${next.height}px`;
      task = page.render({
        canvas: el,
        viewport: next,
        transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : undefined,
      });
      setViewport(next);
      await task.promise.catch(() => undefined);
    })().catch(() => undefined);
    return () => {
      cancelled = true;
      task?.cancel();
    };
    // The highlight is drawn as an overlay, so it never re-renders the canvas.
  }, [shouldRender, doc, number, width]);

  const rects = useMemo(() => {
    if (!viewport || !highlight) return [];
    return highlight.map((item) => {
      const tx = Util.transform(viewport.transform, item.transform);
      const size = Math.hypot(tx[2], tx[3]);
      return {
        left: tx[4] - 2,
        top: tx[5] - size * 0.95,
        width: item.width * viewport.scale + 4,
        height: size * 1.25,
      };
    });
  }, [viewport, highlight]);

  // Center the first highlighted line once it is drawn (inside the PDF pane only).
  useEffect(() => {
    if (!rects.length) return;
    const line = box.current?.querySelector<HTMLElement>(".pdf-hl");
    if (line) scrollInsidePane(line, "center");
  }, [rects, nonce]);

  const height = viewport?.height ?? width * aspect;
  return (
    <div className="pdf-page" id={`pdf-page-${number}`} ref={box} style={{ height, width }}>
      <canvas ref={canvas} />
      {rects.map((r, i) => (
        <span key={i} className="pdf-hl" style={r} />
      ))}
      <span className="pdf-page-no">{number}</span>
    </div>
  );
}
