import { defineTool } from "eve/tools";
import { always } from "eve/tools/approval";
import { z } from "zod";
import { getCustomer } from "#lib/energy_db.js";

export default defineTool({
  description:
    "Book a technician appointment for a Luminus customer (e.g. meter replacement or inspection). " +
    "This schedules a real visit, so it requires human approval before it runs.",
  inputSchema: z.object({
    customerId: z.string().min(1).describe("Luminus account id, e.g. LUM-1001"),
    reason: z.string().min(1).describe("Why the visit is needed, e.g. 'smart meter replacement'"),
    preferredDate: z.string().min(1).describe("Customer's preferred date, ISO 8601 (YYYY-MM-DD)"),
  }),
  // Booking a technician visit is an external side effect -> gate every call on a person.
  approval: always(),
  async execute({ customerId, reason, preferredDate }) {
    const customer = getCustomer(customerId);
    if (!customer) {
      return { booked: false, message: `No Luminus account found for ${customerId}.` };
    }
    const reference = `APPT-${customerId}-${preferredDate.replace(/-/g, "")}`;
    return {
      booked: true,
      reference,
      customer: customer.name,
      reason,
      date: preferredDate,
      message: `Appointment confirmed for ${customer.name} on ${preferredDate} (${reason}). Reference ${reference}.`,
    };
  },
});
