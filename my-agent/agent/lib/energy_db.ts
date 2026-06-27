// Simulated Luminus energy customer database.
// In production this would query your billing / metering systems.

export type Customer = {
  customerId: string;
  name: string;
  plan: "Comfy Fixed" | "Dynamic" | "Solar Buyback";
  lastBillEur: number;
};

const CUSTOMERS: Record<string, Customer> = {
  "LUM-1001": { customerId: "LUM-1001", name: "Sofie", plan: "Comfy Fixed", lastBillEur: 142.5 },
  "LUM-1002": { customerId: "LUM-1002", name: "Marc", plan: "Dynamic", lastBillEur: 208.9 },
  "LUM-1003": { customerId: "LUM-1003", name: "Amira", plan: "Solar Buyback", lastBillEur: 76.2 },
};

export function getCustomer(customerId: string): Customer | undefined {
  return CUSTOMERS[customerId];
}

export function billingExplanation(c: Customer): string {
  return (
    `Account ${c.customerId} (${c.name}, ${c.plan} plan): last bill €${c.lastBillEur.toFixed(2)}. ` +
    `The increase versus your average is driven by higher evening peak-hour usage and a seasonal ` +
    `rate adjustment applied this quarter.`
  );
}

export function energyInsights(c: Customer): string {
  return (
    `${c.name}'s usage peaks on weekday evenings (18:00–22:00) and rises in winter for heating. ` +
    `Standby load from always-on devices accounts for roughly 8% of consumption.`
  );
}

export const SAVING_TIPS = [
  "Shift dishwasher and laundry to off-peak hours (after 22:00) — especially on the Dynamic plan.",
  "Lower the thermostat by 1°C to cut heating costs by ~6%.",
  "Switch standby devices off at the wall to remove always-on load.",
  "Use a smart thermostat schedule so heating is off when nobody is home.",
];
