# SvelteKit Toast Notification Pattern

Reusable toast/popup notification for form submission feedback in SvelteKit.

## Pattern

Bottom-center slide-up toast with auto-dismiss + manual dismiss.

## Component template

```svelte
<script lang="ts">
	let showToast = $state(false);
	let toastMessage = $state('');
	let toastType = $state<'success' | 'error'>('success');

	function showSuccess(msg: string) {
		toastType = 'success';
		toastMessage = msg;
		showToast = true;
		setTimeout(() => showToast = false, 5000);
	}

	function showError(msg: string) {
		toastType = 'error';
		toastMessage = msg;
		showToast = true;
		setTimeout(() => showToast = false, 5000);
	}
</script>

{#if showToast}
	<button
		onclick={() => showToast = false}
		class="fixed bottom-6 left-1/2 -translate-x-1/2 w-[calc(100%-2rem)] max-w-md z-50 
			{toastType === 'success' ? 'bg-green-50 border-green-200 text-green-800' : 'bg-red-50 border-red-200 text-red-800'}
			border rounded-xl px-5 py-4 shadow-lg animate-slide-up cursor-pointer text-left"
	>
		<div class="flex items-start gap-3">
			{#if toastType === 'success'}
				<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="shrink-0 mt-0.5 text-green-600"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
			{:else}
				<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="shrink-0 mt-0.5 text-red-600"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
			{/if}
			<div class="flex-1 min-w-0">
				<p class="text-sm font-medium">{toastType === 'success' ? title : 'Gagal'}</p>
				<p class="text-xs mt-0.5 opacity-80">{toastMessage}</p>
			</div>
			<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="shrink-0 opacity-50"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
		</div>
	</button>
{/if}

<style>
	@keyframes slide-up {
		from { opacity: 0; transform: translate(-50%, 20px); }
		to { opacity: 1; transform: translate(-50%, 0); }
	}
	.animate-slide-up {
		animation: slide-up 0.3s ease-out;
	}
</style>
```

## Key decisions

- **Fixed bottom center** — always visible regardless of scroll position
- **Auto-dismiss 5s + manual tap-to-dismiss** — no blocking overlay
- **Form stays visible** — user can retry immediately on error
- **No JS library** — pure Svelte 5 `$state`, zero deps
- **`<button>` not `<div>`** — accessible, keyboard-focusable

## When to use

- Forgot password confirmation
- Login/register form feedback
- Cart add/remove confirmations
- API key copy success
- Any form submission that currently does a full page reload or shows inline text

## When NOT to use

- Multi-step flows needing user decision (use modal)
- Critical errors that block further action (use inline error near the field)
- Persistent state that must be acknowledged (use banner)
