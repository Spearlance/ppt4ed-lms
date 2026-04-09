<template>
	<div>
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs
				class="h-7"
				:items="[{ label: __('Admin Reports'), route: { name: 'AdminReports' } }]"
			/>
		</header>

		<div class="p-5">
			<Tabs :tabs="tabs" v-model="tabIndex">
				<template #tab-panel="{ tab }">
					<component :is="tab.component" />
				</template>
			</Tabs>
		</div>
	</div>
</template>

<script setup>
import { markRaw, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Breadcrumbs, Tabs, usePageMeta } from 'frappe-ui'
import ReportRevenue from '@/pages/AdminReports/ReportRevenue.vue'
import ReportCoursesTaken from '@/pages/AdminReports/ReportCoursesTaken.vue'
import ReportMembers from '@/pages/AdminReports/ReportMembers.vue'
import ReportUsage from '@/pages/AdminReports/ReportUsage.vue'
import ReportCreditHealth from '@/pages/AdminReports/ReportCreditHealth.vue'
import ReportCoursePerformance from '@/pages/AdminReports/ReportCoursePerformance.vue'
import ReportDisciplineDemand from '@/pages/AdminReports/ReportDisciplineDemand.vue'

const router = useRouter()
const route = useRoute()
const tabIndex = ref(0)

usePageMeta({ title: 'Admin Reports' })

const tabs = ref([
	{ label: 'Revenue', component: markRaw(ReportRevenue) },
	{ label: 'Courses', component: markRaw(ReportCoursesTaken) },
	{ label: 'Members', component: markRaw(ReportMembers) },
	{ label: 'Usage', component: markRaw(ReportUsage) },
	{ label: 'Health', component: markRaw(ReportCreditHealth) },
	{ label: 'Performance', component: markRaw(ReportCoursePerformance) },
	{ label: 'Disciplines', component: markRaw(ReportDisciplineDemand) },
])

watch(tabIndex, () => {
	const tab = tabs.value[tabIndex.value]
	if (tab.label.toLowerCase() !== route.hash.replace('#', '')) {
		router.push({ ...route, hash: `#${tab.label.toLowerCase()}` })
	}
})

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
updateTabIndex()
</script>
