<template>
	<div class="relative flex h-full flex-col">
		<div class="h-full flex-1">
			<div class="flex h-screen text-base bg-surface-white">
				<div
					class="flex w-full flex-col overflow-auto"
					id="scrollContainer"
				>
					<div class="flex-1">
						<slot />
					</div>
					<AppFooter />
				</div>
			</div>
		</div>
	</div>
</template>
<script setup>
import AppFooter from '@/components/AppFooter.vue'
</script>
