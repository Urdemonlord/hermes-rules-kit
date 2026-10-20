/**
 * GoPay Merchant (GoBiz) — QRIS Dynamic Generator + Live Monitor
 * 
 * Usage:
 *   node gobiz-qris-demo.mjs qris 50000       → generate QRIS only (no credentials)
 *   node gobiz-qris-demo.mjs monitor 50000    → login + monitor payments (needs .env)
 * 
 * Requires: npm install gobiz-pay dotenv
 * Requires .env with: GOPAY_EMAIL, GOPAY_PASSWORD, QRIS_STRING
 */

import { GoPayMerchant, buildDynamicQris, generateQrisImage, getGoPayWatcher } from "gobiz-pay";
import { config } from "dotenv";
import { writeFileSync } from "fs";

config();

const mode = process.argv[2] || "qris";
const amount = parseInt(process.argv[3] || "50000");

// ============================================================
// MODE: QRIS GENERATOR (offline — no credentials needed)
// ============================================================
async function modeQris() {
  const qrisStatic = process.env.QRIS_STRING;
  
  if (!qrisStatic || qrisStatic === "0002010102112657...") {
    console.log("❌ QRIS_STRING not set in .env");
    console.log("   Get your static QRIS from GoBiz dashboard > Settings > QRIS");
    console.log("   Format: string starting with 000201...");
    return;
  }

  try {
    const dynamicQris = buildDynamicQris(qrisStatic, amount);
    const buf = await generateQrisImage(dynamicQris);
    const filename = `/tmp/gopay-qris-${amount}.png`;
    writeFileSync(filename, buf);
    
    console.log("✅ QRIS Dinamis Generated");
    console.log(`   Amount  : Rp ${amount.toLocaleString("id-ID")}`);
    console.log(`   Length  : ${dynamicQris.length} chars`);
    console.log(`   Image   : ${filename}`);
    console.log(`   Preview : ${dynamicQris.slice(0, 70)}...`);
  } catch (e) {
    console.log(`❌ Error: ${e.message}`);
  }
}

// ============================================================
// MODE: LIVE MONITOR (needs GoPay credentials)
// ============================================================
async function modeMonitor() {
  const email = process.env.GOPAY_EMAIL;
  const password=<redacted>
  
  if (!email || email === "user@example.com") {
    console.log("❌ GOPAY_EMAIL & GOPAY_PASSWORD not set in .env");
    return;
  }

  const merchant = new GoPayMerchant();
  
  try {
    await merchant.init();
    console.log(`✅ Logged in. Merchant ID: ${merchant.merchantId}`);

    // Recent transactions
    const history = await merchant.getHistory({ days: 7, size: 10 });
    if (history.status && history.data) {
      console.log("\n📊 Recent transactions:");
      history.data.histories.forEach((tx) => {
        console.log(`   ${tx.time} | ${tx.amount.displayed_text}`);
      });
    }

    // Generate QR + monitor payment
    console.log(`\n📱 Monitoring for Rp ${amount.toLocaleString("id-ID")}...`);
    const watcher = getGoPayWatcher();
    
    const payment = await watcher.waitForPayment(amount, {
      timeout: 300_000,
      tolerance: 100,
    });
    console.log(`✅ PAYMENT RECEIVED! TxID: ${payment.txId} | Rp ${payment.amount.toLocaleString("id-ID")}`);
  } catch (e) {
    console.log(`❌ ${e.message}`);
  }
}

// ============================================================
if (mode === "monitor") modeMonitor();
else modeQris();
