const botToken = process.env.TELEGRAM_BOT_TOKEN
const defaultChat = process.env.TELEGRAM_DEFAULT_CHAT

export async function sendTelegramMessage(message: string, chatId = defaultChat) {
  if (!botToken || !chatId) return { ok: false, skipped: true }

  const url = `https://api.telegram.org/bot${botToken}/sendMessage`
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, text: message }),
  })

  const data = await res.json().catch(() => ({}))
  return { ok: res.ok, data }
}
