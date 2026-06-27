import { defineTool } from "eve/tools";
import { z } from "zod";
import { getCustomer, energyInsights, SAVING_TIPS } from "#lib/energy_db.js";

export default defineTool({
  description:
    "Give actionable energy-saving advice tailored to a Luminus customer's usage. " +
    "Use when the customer asks how to lower their bill or reduce consumption.",
  inputSchema: z.object({
    customerId: z.string().min(1).describe("Luminus account id, e.g. LUM-1001"),
    focus: z
      .enum(["heating", "appliances", "general"])
      .default("general")
      .describe("Optional area the customer cares most about."),
  }),
  async execute({ customerId, focus }) {
    const customer = getCustomer(customerId);
    const insights = customer ? energyInsights(customer) : undefined;
    const tips =
      focus === "heating"
        ? SAVING_TIPS.filter((t) => /thermostat|heating|°C/i.test(t))
        : focus === "appliances"
          ? SAVING_TIPS.filter((t) => /dishwasher|laundry|standby|device/i.test(t))
          : SAVING_TIPS;
    return { focus, insights, tips };
  },
});
