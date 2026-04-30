<template>
	<div class="p-5 space-y-6">
		<div class="flex items-center justify-between">
			<h3 class="text-base font-semibold text-ink-gray-9">
				{{ __('Team Activity') }}
			</h3>
			<FormControl
				v-model="periodDays"
				type="select"
				:options="periodOptions"
				class="w-40"
			/>
		</div>

		<div v-if="activity.data" class="grid grid-cols-2 md:grid-cols-4 gap-4">
			<div class="rounded-md border border-outline-gray-2 p-4">
				<div class="text-xs uppercase tracking-wide text-ink-gray-5">
					{{ __('Active learners') }}
				</div>
				<div class="text-2xl font-semibold text-ink-gray-9 mt-1">
					{{ activity.data.totals.active_learners_period }}
					<span class="text-base text-ink-gray-5 font-normal">
						/ {{ activity.data.totals.members }}
					</span>
				</div>
				<div class="text-xs text-ink-gray-5 mt-1">
					{{ __('in last {0} days').format(activity.data.period_days) }}
				</div>
			</div>
			<div class="rounded-md border border-outline-gray-2 p-4">
				<div class="text-xs uppercase tracking-wide text-ink-gray-5">
					{{ __('Courses completed') }}
				</div>
				<div class="text-2xl font-semibold text-ink-gray-9 mt-1">
					{{ activity.data.totals.completed_period }}
				</div>
				<div class="text-xs text-ink-gray-5 mt-1">
					{{ __('{0} lifetime').format(activity.data.totals.completed_total) }}
				</div>
			</div>
			<div class="rounded-md border border-outline-gray-2 p-4">
				<div class="text-xs uppercase tracking-wide text-ink-gray-5">
					{{ __('CEU credits used') }}
				</div>
				<div class="text-2xl font-semibold text-ink-gray-9 mt-1">
					{{ formatHours(activity.data.totals.ceu_debited_period) }}
				</div>
				<div class="text-xs text-ink-gray-5 mt-1">
					{{ __('in last {0} days').format(activity.data.period_days) }}
				</div>
			</div>
			<div class="rounded-md border border-outline-gray-2 p-4">
				<div class="text-xs uppercase tracking-wide text-ink-gray-5">
					{{ __('Avg credits / employee') }}
				</div>
				<div class="text-2xl font-semibold text-ink-gray-9 mt-1">
					{{ formatHours(activity.data.totals.avg_ceu_per_member_period) }}
				</div>
				<div class="text-xs text-ink-gray-5 mt-1">
					{{ __('across {0} employees').format(activity.data.totals.members) }}
				</div>
			</div>
		</div>

		<div v-if="activity.data?.members?.length">
			<h4 class="text-sm font-semibold text-ink-gray-9 mb-2">
				{{ __('Per-employee breakdown') }}
			</h4>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b text-left text-ink-gray-5">
							<th class="pb-2 pr-4 font-medium">{{ __('Employee') }}</th>
							<th class="pb-2 pr-4 font-medium text-right">
								{{ __('In progress') }}
							</th>
							<th class="pb-2 pr-4 font-medium text-right">
								{{ __('Completed (period)') }}
							</th>
							<th class="pb-2 pr-4 font-medium text-right">
								{{ __('Completed (total)') }}
							</th>
							<th class="pb-2 pr-4 font-medium text-right">
								{{ __('Credits used') }}
							</th>
							<th class="pb-2 font-medium">{{ __('Last active') }}</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="m in activity.data.members"
							:key="m.user"
							class="border-b last:border-0"
						>
							<td class="py-3 pr-4">
								<div class="font-medium text-ink-gray-9">{{ m.full_name }}</div>
								<div class="text-xs text-ink-gray-5">{{ m.email }}</div>
							</td>
							<td class="py-3 pr-4 text-right text-ink-gray-7">
								{{ m.in_progress }}
							</td>
							<td class="py-3 pr-4 text-right text-ink-gray-7">
								{{ m.completed_period }}
							</td>
							<td class="py-3 pr-4 text-right text-ink-gray-5">
								{{ m.completed_total }}
							</td>
							<td class="py-3 pr-4 text-right text-ink-gray-7">
								{{ formatHours(m.ceu_debited_period) }}
							</td>
							<td class="py-3 text-ink-gray-5">
								{{
									m.last_active ? dayjs(m.last_active).fromNow() : __('Never')
								}}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<div v-if="activity.data?.top_courses?.length">
			<h4 class="text-sm font-semibold text-ink-gray-9 mb-2">
				{{ __('Top courses across the team') }}
			</h4>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b text-left text-ink-gray-5">
							<th class="pb-2 pr-4 font-medium">{{ __('Course') }}</th>
							<th class="pb-2 pr-4 font-medium text-right">
								{{ __('Enrolled') }}
							</th>
							<th class="pb-2 font-medium text-right">
								{{ __('Completed') }}
							</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="c in activity.data.top_courses"
							:key="c.course"
							class="border-b last:border-0"
						>
							<td class="py-3 pr-4 font-medium text-ink-gray-9">
								{{ c.title }}
							</td>
							<td class="py-3 pr-4 text-right text-ink-gray-7">
								{{ c.enrollment_count }}
							</td>
							<td class="py-3 text-right text-ink-gray-7">
								{{ c.completed_count }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<div
			v-else-if="activity.loading"
			class="text-center py-10 text-ink-gray-5"
		>
			{{ __('Loading...') }}
		</div>
		<div
			v-else-if="!activity.data?.members?.length"
			class="text-center py-10 text-ink-gray-5"
		>
			{{ __('No employees yet — invite some to start tracking activity.') }}
		</div>
	</div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { createResource, FormControl } from 'frappe-ui'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'

dayjs.extend(relativeTime)

const periodDays = ref(30)
const periodOptions = [
	{ label: __('Last 7 days'), value: 7 },
	{ label: __('Last 30 days'), value: 30 },
	{ label: __('Last 90 days'), value: 90 },
	{ label: __('Last 365 days'), value: 365 },
]

const activity = createResource({
	url: 'lms.lms.ceu_company_dashboard.get_team_activity',
	makeParams() {
		return { period_days: periodDays.value }
	},
	cache: ['company-team-activity'],
	auto: true,
})

watch(periodDays, () => {
	activity.reload()
})

const formatHours = (h) => {
	const n = Number(h || 0)
	return n % 1 === 0 ? n.toFixed(0) : n.toFixed(1)
}
</script>
