import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AgentActivityCluster } from "@/components/thread/AgentActivityCluster";
import {
  FoodResultCard,
  foodArtSrc,
  parseFoodPresentation,
  type FoodPresentation,
} from "@/components/thread/FoodResultCard";
import type { UIMessage } from "@/lib/types";

const suggest: FoodPresentation = {
  image_policy: "schematic_local",
  photograph: false,
  cards: [{
    art_id: "tomato-egg",
    alt: "番茄炒蛋示意图",
    title: "番茄炒蛋",
    meta: "2人 · 约15分钟",
    ingredients: ["鸡蛋", "番茄"],
  }],
  shopping: [],
  notice: "图片是示意图，不是实拍。",
  web_markdown: "![番茄炒蛋示意图](/food-art/tomato-egg.svg)",
  feishu_text: "1. 番茄炒蛋",
  reply_markdown: "![番茄炒蛋示意图](/food-art/tomato-egg.svg)",
};

describe("FoodResultCard", () => {
  it("renders an allowlisted schematic in a single-column mobile layout", () => {
    render(<FoodResultCard presentation={suggest} />);

    const image = screen.getByRole("img", { name: "番茄炒蛋示意图" });
    expect(image).toHaveAttribute("src", "/food-art/tomato-egg.svg");
    expect(screen.getByText("番茄炒蛋")).toBeInTheDocument();
    expect(screen.getByText("2人 · 约15分钟")).toBeInTheDocument();
    expect(screen.getByText("关键食材：鸡蛋、番茄")).toBeInTheDocument();
    expect(screen.getByTestId("food-result").querySelector(".grid")).toHaveClass("grid-cols-1");
    expect(screen.getByTestId("food-result").querySelector("table")).toBeNull();
  });

  it("drops unsafe image ids and remote URLs", () => {
    expect(foodArtSrc("../secret")).toBeNull();
    expect(foodArtSrc("https://evil.example/a.svg")).toBeNull();
    expect(foodArtSrc("/food-art/tomato-egg.svg")).toBeNull();
    const parsed = parseFoodPresentation({
      presentation: {
        ...suggest,
        cards: [{ ...suggest.cards[0], art_id: "https://evil.example/a.svg" }],
      },
    });
    expect(parsed?.cards).toEqual([]);
    render(<FoodResultCard presentation={parsed!} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("shows text when the schematic file is missing", () => {
    render(<FoodResultCard presentation={suggest} />);
    fireEvent.error(screen.getByRole("img", { name: "番茄炒蛋示意图" }));
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText("番茄炒蛋示意图")).toBeInTheDocument();
  });

  it("does not render a picture or steps for a blocked recipe", () => {
    render(
      <FoodResultCard
        presentation={{
          ...suggest,
          image_policy: "none",
          cards: [],
          notice: "这道菜碰到已确认的过敏原，已经停住，不提供做法。",
        }}
      />,
    );
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
    expect(screen.getByText(/不提供做法/)).toBeInTheDocument();
  });

  it("renders a category shopping list without a table", () => {
    render(
      <FoodResultCard
        presentation={{
          ...suggest,
          image_policy: "none",
          cards: [],
          shopping: [{ category: "蔬菜", lines: ["番茄 2个"] }, { category: "肉蛋海鲜", lines: ["鸡蛋 1个"] }],
        }}
      />,
    );
    expect(screen.getByText("蔬菜")).toBeInTheDocument();
    expect(screen.getByText("- 番茄 2个")).toBeInTheDocument();
    expect(screen.getByTestId("food-result").querySelector("table")).toBeNull();
  });

  it("shows the food card from a webui tool event", () => {
    const message: UIMessage = {
      id: "food-1",
      role: "tool",
      kind: "trace",
      content: "food()",
      traces: ["food()"],
      createdAt: 1,
      toolEvents: [{
        phase: "end",
        call_id: "food-call",
        name: "food",
        result: JSON.stringify({ presentation: suggest }),
      }],
    };
    render(
      <AgentActivityCluster
        messages={[message]}
        isTurnStreaming={false}
        hasBodyBelow={false}
      />,
    );
    expect(screen.getByRole("img", { name: "番茄炒蛋示意图" })).toHaveAttribute(
      "src",
      "/food-art/tomato-egg.svg",
    );
  });
});
