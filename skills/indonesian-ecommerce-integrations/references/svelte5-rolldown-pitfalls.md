# Svelte 5 Build Pitfalls (rolldown)

## `{@const}` inside `{#each}` causes build failure

### Symptom
```
Error: Build failed
  at aggregateBindingErrorsIntoJsError
  ...
  {#each steps as step, i}
```

### Root cause
In Svelte 5 with rolldown, using `{@const}` to bind a variable from an `{#each}` iteration variable can cause build failures:
```svelte
{#each results as order}       <!-- ✗ This pattern fails -->
  {@const steps = fn(order)}   <!-- ✗ {@const} computed from #each variable -->
  {#each steps as step}
    ...
  {/each}
{/each}
```

### Fix: Call function inline
```svelte
{#each results as order}       <!-- ✓ This pattern works -->
  {#each fn(order) as step}    <!-- ✓ Call function directly in #each -->
    ...
  {/each}
{/each}
```

### Alternative: Pre-compute in script
```typescript
// When optimization matters (function is expensive)
function enrichedResults(data: any[]) {
  return data.map(order => ({
    ...order,
    steps: timelineSteps(order)  // Compute once
  }))
}
```

## Double `<script>` tag issues
Having two `<script>` blocks in a Svelte file with imports in the second can cause build confusion. Always merge into one:
```svelte
<!-- ✓ Correct -->
<script lang="ts">
  import { config } from '$lib/config'
  let state = $state('')
</script>

<!-- ✗ This can confuse rolldown -->
<script lang="ts">
  let state = $state('')
</script>
<script lang="ts">
  import { config } from '$lib/config'
</script>
```
