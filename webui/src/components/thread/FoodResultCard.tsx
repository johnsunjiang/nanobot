import { useState } from "react";

import type { ToolProgressEvent } from "@/lib/types";

const ART_IDS = new Set([
  "garlic-lettuce",
  "tomato-egg",
  "pepper-potato",
  "seaweed-egg-soup",
  "egg-fried-rice",
  "braised-tofu",
  "rice",
  "shrimp",
  "tomato-meat-noodles",
  "peanut-salad",
]);

export interface FoodCardData {
  art_id: string;
  alt: string;
  title: string;
  meta: string;
  ingredients: string[];
  steps?: string[];
}

export interface FoodShoppingGroup {
  category: string;
  lines: string[];
}

export interface FoodPresentation {
  image_policy: "none" | "schematic_local";
  photograph: false;
  cards: FoodCardData[];
  shopping: FoodShoppingGroup[];
  notice: string;
  web_markdown: string;
  feishu_text: string;
  reply_markdown: string;
}

export function foodArtSrc(artId: unknown): string | null {
  if (typeof artId !== "string" || !ART_IDS.has(artId)) return null;
  return `/food-art/${artId}.svg`;
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

function parseCard(value: unknown): FoodCardData | null {
  if (!value || typeof value !== "object") return null;
  const card = value as Record<string, unknown>;
  if (typeof card.title !== "string" || !card.title.trim()) return null;
  if (foodArtSrc(card.art_id) === null) return null;
  return {
    art_id: card.art_id as string,
    alt: typeof card.alt === "string" && card.alt.trim() ? card.alt : `${card.title}示意图`,
    title: card.title,
    meta: typeof card.meta === "string" ? card.meta : "",
    ingredients: asStringList(card.ingredients),
    steps: asStringList(card.steps),
  };
}

export function parseFoodPresentation(result: unknown): FoodPresentation | null {
  const payload = typeof result === "string" ? parseJson(result) : result;
  if (!payload || typeof payload !== "object") return null;
  const record = payload as Record<string, unknown>;
  const raw = record.presentation;
  if (!raw || typeof raw !== "object") return null;
  const presentation = raw as Record<string, unknown>;
  if (presentation.image_policy !== "none" && presentation.image_policy !== "schematic_local") return null;
  const cards = presentation.image_policy === "schematic_local"
    ? (Array.isArray(presentation.cards) ? presentation.cards.map(parseCard).filter((card): card is FoodCardData => card !== null) : [])
    : [];
  const shopping = Array.isArray(presentation.shopping)
    ? presentation.shopping.flatMap((group) => {
        if (!group || typeof group !== "object") return [];
        const item = group as Record<string, unknown>;
        if (typeof item.category !== "string") return [];
        const lines = asStringList(item.lines);
        return lines.length ? [{ category: item.category, lines }] : [];
      })
    : [];
  if (presentation.image_policy === "none" && cards.length === 0 && shopping.length === 0 && typeof presentation.notice !== "string") {
    return null;
  }
  return {
    image_policy: cards.length ? "schematic_local" : "none",
    photograph: false,
    cards,
    shopping,
    notice: typeof presentation.notice === "string" ? presentation.notice : "",
    web_markdown: typeof presentation.web_markdown === "string" ? presentation.web_markdown : "",
    feishu_text: typeof presentation.feishu_text === "string" ? presentation.feishu_text : "",
    reply_markdown: typeof presentation.reply_markdown === "string" ? presentation.reply_markdown : "",
  };
}

function parseJson(value: string): unknown {
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return null;
  }
}

export function foodPresentationsFromMessages(
  messages: { toolEvents?: ToolProgressEvent[] }[],
): FoodPresentation[] {
  const found: FoodPresentation[] = [];
  for (const message of messages) {
    for (const event of message.toolEvents ?? []) {
      if (event.name !== "food" || event.phase === "start") continue;
      const presentation = parseFoodPresentation(event.result);
      if (presentation) found.push(presentation);
    }
  }
  return found;
}

function FoodArt({ artId, alt }: { artId: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  const src = foodArtSrc(artId);
  if (!src || failed) {
    return <p className="text-sm text-muted-foreground">{alt}</p>;
  }
  return (
    <img
      src={src}
      alt={alt}
      width={160}
      height={120}
      decoding="async"
      className="h-28 w-full rounded-lg bg-muted/40 object-contain"
      onError={() => setFailed(true)}
    />
  );
}

export function FoodResultCard({ presentation }: { presentation: FoodPresentation }) {
  const showImages = presentation.image_policy === "schematic_local" && presentation.cards.length > 0;
  return (
    <section data-testid="food-result" className="my-2 w-full min-w-0 space-y-3 text-reading">
      {presentation.notice ? <p className="text-sm text-muted-foreground">{presentation.notice}</p> : null}
      {showImages ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {presentation.cards.map((card) => (
            <article key={`${card.art_id}-${card.title}`} className="min-w-0 rounded-xl border border-border/70 p-3">
              <FoodArt artId={card.art_id} alt={card.alt} />
              <h3 className="mt-2 text-base font-medium">{card.title}</h3>
              {card.meta ? <p className="text-sm text-muted-foreground">{card.meta}</p> : null}
              {card.ingredients.length ? (
                <p className="mt-1 break-words text-sm">
                  {card.steps?.length ? "用量" : "关键食材"}：{card.ingredients.join("、")}
                </p>
              ) : null}
              {card.steps?.length ? (
                <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">
                  {card.steps.map((step) => <li key={step}>{step}</li>)}
                </ol>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}
      {presentation.shopping.length ? (
        <div className="space-y-2">
          {presentation.shopping.map((group) => (
            <div key={group.category} className="min-w-0">
              <h3 className="text-sm font-medium">{group.category}</h3>
              <ul className="mt-1 space-y-1 text-sm">
                {group.lines.map((line) => <li key={line} className="break-words">- {line}</li>)}
              </ul>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
