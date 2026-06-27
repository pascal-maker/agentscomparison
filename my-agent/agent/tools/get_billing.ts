import { defineTool } from "eve/tools";
import { z } from "zod";
import { getCustomer, billingExplanation, energyInsights } from "#lib/energy_db.js";

export default defineTool({
  description:
    "Look up a Luminus customer's latest bill and explain it, including usage insights. " +
    "Use when a customer asks about their bill, charges, or why their bill changed.",
  inputSchema: z.object({
    customerId: z.string().min(1).describe("Luminus account id, e.g. LUM-1001"),
  }),
  async execute({ customerId }) {
    const customer = getCustomer(customerId);
    if (!customer) {
      return { found: false, message: `No Luminus account found for ${customerId}.` };
    }
    return {
      found: true,
      customer: { id: customer.customerId, name: customer.name, plan: customer.plan },
      lastBillEur: customer.lastBillEur,
      explanation: billingExplanation(customer),
      insights: energyInsights(customer),
    };
  },
});
