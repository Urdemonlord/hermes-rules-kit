# Toast Notification Pattern for Login UX (SvelteKit)

## When to use this reference
Adding login/logout/register feedback or any auth-flow toast notification to a SvelteKit ecommerce app.

## Core concept
Don't `throw redirect()` in the server action — return data instead. Use `sessionStorage` as a bridge for the flash message across page navigation.

## Files needed

### 1. Toast store — `src/lib/stores/toast.ts`
```ts
import { writable } from 'svelte/store';

export type Toast = {
    id: string;
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
    duration?: number;
};

export const toastStore = createToastStore();

export const toast = {
    success: (m: string, d = 3000) => toastStore.add({ message: m, type: 'success', duration: d }),
    error: (m: string, d = 4000) => toastStore.add({ message: m, type: 'error', duration: d }),
    info: (m: string, d = 3000) => toastStore.add({ message: m, type: 'info', duration: d }),
    warning: (m: string, d = 3500) => toastStore.add({ message: m, type: 'warning', duration: d }),
};

function createToastStore() {
    const { subscribe, set, update } = writable<Toast[]>([]);
    return {
        subscribe,
        add: (toast: Omit<Toast, 'id'>) => {
            const id = Math.random().toString(36).slice(2);
            const newToast: Toast = { id, duration: 3000, ...toast };
            update((t) => [...t, newToast]);
            if (newToast.duration) setTimeout(() => update((t) => t.filter((x) => x.id !== id)), newToast.duration);
            return id;
        },
        remove: (id: string) => update((t) => t.filter((x) => x.id !== id)),
        clear: () => set([]),
    };
}
```

### 2. Toast component — `src/lib/components/Toast.svelte`
Fixed top-right, animated slide-in, dismissable. Subscribe to `toastStore`, render each as colored banner with icon + close button. Auto-animate out.

### 3. Layout — `src/routes/+layout.svelte`
Mount `<Toast />` inside the wrapper div. Add onMount to read sessionStorage:
```ts
onMount(() => {
    try {
        const flash = sessionStorage.getItem('flash_toast');
        if (flash) {
            const { message, type } = JSON.parse(flash);
            toast[type || 'success'](message);
            sessionStorage.removeItem('flash_toast');
        }
    } catch { /* ignore */ }
});
```

### 4. Login server action — return instead of throw
```ts
// BEFORE (breaks client-side handler):
throw redirect(302, '/')

// AFTER (enables toast):
return { success: true, userName: user.displayName || user.email }
```

### 5. Login page client — intercept success
```ts
import { applyAction } from '$app/forms';
import { goto } from '$app/navigation';

<form method="POST" use:enhance={() => {
    loading = true;
    return async ({ result }) => {
        loading = false;
        if (result.type === 'success') {
            sessionStorage.setItem('flash_toast', JSON.stringify({
                message: `Berhasil login. Selamat datang kembali, ${form?.userName || 'Pengguna'}!`,
                type: 'success'
            }));
            goto('/');
        } else {
            await applyAction(result);
        }
    };
}}>
```

## Indonesian ecommerce toast messages
- Login: `Berhasil login. Selamat datang kembali, {nama}!`
- Logout: `Berhasil keluar dari akun`
- Register: `Akun berhasil dibuat!`
- Add to cart: `Ditambahkan ke keranjang`
- Order: `Pesanan berhasil dibuat`
- Error: `Terjadi kesalahan, silakan coba lagi`

## Key pitfall
`redirect()` in server action kills the client enhance handler — can't intercept. Return data instead, handling redirection client-side with `goto()`.

## Applies to
- Login, logout, register, password reset
- Admin CRUD actions (add/edit/delete product)
- Cart actions (add/remove/update)
- Order creation