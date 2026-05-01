<template>
	<div class="flex h-screen w-screen">
		<div class="h-full border-r bg-surface-menu-bar">
			<AppSidebar />
		</div>
		<div class="flex-1 flex flex-col h-full overflow-auto bg-surface-white">
			<div class="flex-1">
				<slot />
			</div>
			<AppFooter />
		</div>
	</div>
</template>
<script setup>
import AppSidebar from '@/components/Sidebar/AppSidebar.vue'
import AppFooter from '@/components/AppFooter.vue'
</script>
