<template>
	<div v-if="dashboard.data">
		<header
			class="sticky top-0 z-10 border-b flex items-center justify-between bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs
				:items="[
					{ label: __('Company Dashboard'), route: { name: 'CompanyDashboard' } },
				]"
			/>
		</header>
		<div class="px-5 pt-4">
			<div class="flex items-center justify-between mb-4">
				<div>
					<h2 class="text-xl font-semibold text-ink-gray-9">
						{{ dashboard.data.company_name }}
					</h2>
					<p class="text-sm text-ink-gray-5 mt-1">
						{{ dashboard.data.member_count }} members · {{ dashboard.data.admin_count }} admins
						<template v-if="dashboard.data.membership">
							· {{ dashboard.data.membership.credit_balance }} credits available
						</template>
					</p>
				</div>
				<Badge
					v-if="dashboard.data.membership"
					:theme="dashboard.data.membership.status === 'Active' ? 'green' : 'orange'"
				>
					{{ dashboard.data.membership.status }}
				</Badge>
			</div>
		</div>
		<Tabs :tabs="tabs" v-model="tabIndex">
			<template #tab-panel="{ tab }">
				<component :is="tab.component" />
			</template>
		</Tabs>
	</div>
	<div v-else-if="dashboard.loading" class="flex justify-center py-20">
		<p class="text-ink-gray-5">{{ __('Loading...') }}</p>
	</div>
</template>

<script setup>
import { markRaw, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Badge, Breadcrumbs, Tabs, usePageMeta, createResource } from 'frappe-ui'
import CompanyEmployees from '@/pages/CompanyDashboard/CompanyEmployees.vue'
import CompanyInvites from '@/pages/CompanyDashboard/CompanyInvites.vue'
import CompanyCreditHistory from '@/pages/CompanyDashboard/CompanyCreditHistory.vue'
import CompanyEnrollmentRequests from '@/pages/CompanyDashboard/CompanyEnrollmentRequests.vue'
import CompanyBilling from '@/pages/CompanyDashboard/CompanyBilling.vue'

const router = useRouter()
const route = useRoute()
const tabIndex = ref(0)

usePageMeta({ title: 'Company Dashboard' })

const dashboard = createResource({
	url: 'lms.lms.ceu_company_dashboard.get_company_dashboard',
	cache: ['company-dashboard'],
	auto: true,
})

const tabs = ref([
	{ label: 'Employees', component: markRaw(CompanyEmployees) },
	{ label: 'Invitations', component: markRaw(CompanyInvites) },
	{ label: 'Credits', component: markRaw(CompanyCreditHistory) },
	{ label: 'Requests', component: markRaw(CompanyEnrollmentRequests) },
	{ label: 'Billing', component: markRaw(CompanyBilling) },
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

watch(dashboard, () => {
	updateTabIndex()
})
</script>
