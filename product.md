# VoltNet
## A Decentralized Peer-to-Peer (P2P) Micro-Grid Energy Market-Clearing Engine.


**What is Peer to Peer Energy Trading?**<br/>
P2P energy trading is enables grid-connected users to buy and sell excess energy directly with others through a secure platform, giving customers the freedom to choose their energy buyers and sellers. 



* **Do all the people have to be connected to the grid to be consumers?**
Yes, they must share a physical distribution grid line to receive the electrons, but they don't need their own generation setups.
* **Do all the people have to be producers to be a part of the grid?**
No, pure consumers (houses without solar panels) participate solely to buy cheaper local green energy.
* **What if someone doesn't want to buy electricity from another person, can they just wait?**
Yes, their local battery storage can handle their load, and they only submit buy bids when their local storage drops below a critical safety threshold.
* **Can a user block other producers from selling to hike up their own prices?**
In a true open market, no—but We can implement local firewall preferences where users choose *who* they buy from (e.g., "Only buy from my neighborhood").
* **How scalable is this?**
Highly scalable if decentralized; using a localized edge-matching architecture ensures regional microgrids don't bog down a central server.
* **What is the USP (Unique Selling Proposition) of this product?**
It eliminates the massive middleman markup of traditional utility monopolies, giving producers 30% higher returns and consumers 20% cheaper power.
* **Has anyone done this successfully before?**
Yes, commercial companies like **Powerledger** (running active pilots with Tata Power in India) and **LO3 Energy** (with the Brooklyn Microgrid) have proven this works.
* **What benefit do I as a house owner have from this?**
We monetize Our idle roof space at premium rates during peak evening hours instead of selling it back to the utility company for pennies.
* **What are the stop valves if the prices spiral out of control?**
The system uses automatic **price caps** and fallback triggers that automatically route power from the main central utility grid if local auction prices exceed a set limit.
* **What measures ensure the security of an autonomous marketplace dominated by algorithms?**
Cryptographic smart contracts lock in matching rules, while IoT smart meters cryptographically sign data payloads to prevent users from faking their energy generation metrics.



---

## 1. What We Are Actually *Building* (The Software Product)

We are building an **Autonomous Localized Energy Exchange (ALEX)** platform.

It is a market layer that integrates with existing grid hardware (smart meters). Instead of building physical cables or power lines, our code acts as the **distributed operating system** that runs on top of the physical grid.

### The Core Software Stack Includes:

* **The Aggregator Engine:** Connects to physical or simulated IoT smart meters at each household to read real-time energy production (solar) and consumption data.
* **The Matching Engine (The Order Book):** A high-throughput double-auction algorithm that updates every time-block (e.g., every 15 minutes). It ingests all local buy/sell requests, matches them based on price optimizations, and discovers the market-clearing price.
* **The Settlement & Billing Layer:** A secure, cryptographic ledger (like a local blockchain or state channel) that records every micro-transaction. At the end of the month, it outputs a clean programmatic invoice that integrates directly into the local power distribution company’s (DISCOM) billing system via open APIs.

---

## 2. What We Are Actually *Selling* (The Value & Commodity)

We aren't selling solar panels or electricity directly—the users already own or use those. we are selling **users a way to sell their excess electricity or buy from others at a cheaper rate during the day.**. At night, users have to fall back to the main line grid.

```
[Traditional Centralized Model]
Prosumer ──(Sells surplus at heavy discount)──► Big Utility DISCOM ──(Sells at 3x markup)──► Neighboring Consumer

[Our Decentralized Model (VoltNet)]
Prosumer ◄───(Direct P2P Trade at Fair Market Clearing Price)───► Neighboring Consumer
                  ▲                                   ▲
                  └─────── Paid to Our Platform ─────┘
                           (Transaction fee per kWh)

```

Specifically, We sell to three distinct groups:

### A. To the House Owner (The Consumer & Prosumer)

* **What we sell them:** **A Yield-Maximization Tool.**
* **The Value:** Currently, if a house owner has excess solar energy, the central grid buys it back via net-metering for a fraction of the cost (e.g., ₹3/unit), but charges their neighbor full price (e.g., ₹8/unit) to consume it. We sell the software that lets the solar owner cut out the middleman, selling it directly to their neighbor for ₹6/unit. The seller makes 100% more profit, and the buyer gets a 25% discount.

### B. To the Electrical Utilities (The DISCOMs)

* **What We sell them:** **Grid Stability & Peak-Load Shaving Software.**
* **The Value:** When everyone turns on their ACs at 7 PM, traditional transformers get heavily overloaded. By incentivizing neighbors to draw power from local residential batteries instead of pulling it all from the main substation, Our software drastically reduces grid congestion and prevents transformer blowouts. We charge the utility an enterprise licensing or management fee.

### C. Our Monetization Strategy (How Our Platform Makes Money)

* **The Transaction Fee:** We charge a micro-tariff on every single traded kilowatt-hour (kWh). For instance, in current real-world frameworks (like the recent regulatory pilots under the *India Energy Stack* framework), a platform transaction fee of roughly **₹0.42 per kWh** is split evenly between the buyer and the seller for using the platform to clear the trade.

> **The Pitch in One Sentence:** We are building the **"Uber for Electrons"**—a highly secure, algorithmic matching infrastructure that allows residential smart meters to autonomously buy and sell clean energy among neighbors, turning passive consumers into an active, localized virtual power plant.