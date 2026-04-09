<template>
	<div v-if="company.data">
		<header
			class="sticky top-0 z-10 border-b flex items-center justify-between bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs
				:items="[
					{ label: __('Companies'), route: { name: 'Settings', query: { tab: 'Companies' } } },
					{ label: company.data.company_name, route: { name: 'CompanyAdmin', params: { companyName } } },
				]"
			/>
		</header>
		<div class="px-5 pt-4">
			<div class="flex items-center justify-between mb-4">
				<div>
					<h2 class="text-xl font-semibold text-ink-gray-9">
						{{ company.data.company_name }}
					</h2>
					<p class="text-sm text-ink-gray-5 mt-1">
						{{ company.data.members?.length || 0 }} members ·
						{{ company.data.admins?.length || 0 }} admins
						<template v-if="company.data.membership">
							· {{ company.data.membership.credit_balance }} credits available
						</template>
					</p>
				</div>
				<Badge
					:theme="company.data.status === 'Active' ? 'green' : company.data.status === 'Suspended' ? 'orange' : 'red'"
				>
					{{ company.data.status }}
				</Badge>
			</div>
		</div>
		<Tabs :tabs="tabs" v-model="tabIndex">
			<template #tab-panel="{ tab }">
				<component :is="tab.component" :company="company" />
			</template>
		</Tabs>
	</div>
	<div v-else-if="company.loading" class="flex justify-center py-20">
		<p class="text-ink-gray-5">{{ __('Loading...') }}</p>
	</div>
	<div v-else-if="company.error" class="flex justify-center py-20">
		<p class="text-red-500">{{ __('Failed to load company details.') }}</p>
	</div>
</template>

<script setup>
import { markRaw, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Badge, Breadcrumbs, Tabs, usePageMeta, createResource } from 'frappe-ui'
import CompanyAdminOverview from '@/pages/CompanyAdmin/CompanyAdminOverview.vue'
import CompanyAdminMembers from '@/pages/CompanyAdmin/CompanyAdminMembers.vue'
import CompanyAdminCredits from '@/pages/CompanyAdmin/CompanyAdminCredits.vue'
import CompanyAdminBilling from '@/pages/CompanyAdmin/CompanyAdminBilling.vue'

const props = defineProps({
	companyName: {
		type: String,
		required: true,
	},
})

const router = useRouter()
const route = useRoute()
const tabIndex = ref(0)

usePageMeta({ title: 'Company Admin' })

const company = createResource({
	url: 'lms.lms.ceu_admin.get_company_admin_details',
	params: { company: props.companyName },
	cache: [`company-admin-${props.companyName}`],
	auto: true,
})

const tabs = ref([
	{ label: 'Overview', component: markRaw(CompanyAdminOverview) },
	{ label: 'Members', component: markRaw(CompanyAdminMembers) },
	{ label: 'Credits', component: markRaw(CompanyAdminCredits) },
	{ label: 'Billing', component: markRaw(CompanyAdminBilling) },
])

const updateTabIndex = () => {
	const hash = route.hash
	if (hash) {
		tabs.value.forEach((tab, index) => {
			if (tab.label?.toLowerCase() === hash.replace('#', '')) {
				tabIndex.value = index
			}
		})
	}
}

watch(tabIndex, () => {
	const tab = tabs.value[tabIndex.value]
	if (tab.label.toLowerCase() !== route.hash.replace('#', '')) {
		router.push({ ...route, hash: `#${tab.label.toLowerCase()}` })
	}
})

watch(company, () => {
	updateTabIndex()
})
</script>
