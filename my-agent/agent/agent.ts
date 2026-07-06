import { openai } from "@ai-sdk/openai";
import { defineAgent } from "eve";

export default defineAgent({
  model: openai("gpt-5"),
  modelContextWindowTokens: 400_000,
});
