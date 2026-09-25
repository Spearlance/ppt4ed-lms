<template>
	<div class="p-5 space-y-6">
		<div class="flex flex-wrap items-end gap-3">
			<FormControl v-model="fromDate" :label="__('From')" type="date" class="w-40" />
			<FormControl v-model="toDate" :label="__('To')" type="date" class="w-40" />
			<div class="grow" />
			<Button size="sm" variant="subtle" @click="downloadCsv">
				{{ __('Export CSV') }}
			</Button>
		</div>

		<div v-if="stats.data?.by_month?.length">
			<h3 class="mb-2 text-base font-semibold text-ink-gray-9">
				{{ __('Every month') }}
			</h3>
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b text-left text-ink-gray-5">
						<th class="pb-2 pr-4 font-medium">{{ __('Month') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('Enrollments') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('People') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('Completions') }}</th>
						<th class="pb-2 font-medium text-right">{{ __('CEU hours issued') }}</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="row in stats.data.by_month"
						:key="row.period"
						class="border-b last:border-0"
					>
						<td class="py-2 pr-4 font-medium text-ink-gray-9">{{ row.period }}</td>
						<td class="py-2 pr-4 text-right text-ink-gray-7">{{ row.enrollments }}</td>
						<td class="py-2 pr-4 text-right text-ink-gray-7">{{ row.members }}</td>
						<td class="py-2 pr-4 text-right text-ink-gray-7">{{ row.completions }}</td>
						<td class="py-2 text-right font-mono text-ink-gray-9">
							{{ row.ceu_hours_issued }}
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<div>
			<h3 class="mb-2 text-base font-semibold text-ink-gray-9">
				{{ __('Month by course') }}
			</h3>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b text-left text-ink-gray-5">
							<th class="pb-2 pr-4 font-medium">{{ __('Month') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Course') }}</th>
							<th class="pb-2 pr-4 font-medium text-right">{{ __('Enrollments') }}</th>
							<th class="pb-2 pr-4 font-medium text-right">{{ __('Completions') }}</th>
							<th class="pb-2 font-medium text-right">{{ __('CEU hours issued') }}</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="row in stats.data?.rows || []"
							:key="`${row.period}-${row.course}`"
							class="border-b last:border-0"
						>
							<td class="py-2 pr-4 text-ink-gray-7">{{ row.period }}</td>
							<td class="py-2 pr-4 font-medium text-ink-gray-9">
								{{ row.course_title || row.course }}
							</td>
							<td class="py-2 pr-4 text-right text-ink-gray-7">{{ row.enrollments }}</td>
							<td class="py-2 pr-4 text-right text-ink-gray-7">{{ row.completions }}</td>
							<td class="py-2 text-right font-mono text-ink-gray-9">
								{{ row.ceu_hours_issued }}
							</td>
						</tr>
						<tr v-if="!stats.data?.rows?.length && !stats.loading">
							<td class="py-6 text-center text-ink-gray-5" colspan="5">
								{{ __('No enrollments in this range.') }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
			<p class="mt-3 text-xs text-ink-gray-5">
				{{ __('Resources are excluded. CEU hours are counted when a course is completed.') }}
			</p>
		</div>
	</div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Button, FormControl, createResource, toast } from 'frappe-ui'

const iso = (d) => d.toISOString().slice(0, 10)

const monthsAgo = (n) => {
	const d = new Date()
	d.setMonth(d.getMonth() - n)
	return d
}

const fromDate = ref(iso(monthsAgo(12)))
const toDate = ref(iso(new Date()))

const stats = createResource({
	url: 'lms.lms.ceu_reports.get_monthly_course_stats',
	makeParams: () => ({ from_date: fromDate.value, to_date: toDate.value }),
	auto: true,
})

let reloadTimer = null
watch([fromDate, toDate], () => {
	clearTimeout(reloadTimer)
	reloadTimer = setTimeout(() => stats.reload(), 250)
})

const downloadCsv = () => {
	const rows = stats.data?.rows || []
	if (!rows.length) {
		toast.error(__('Nothing to export for this range.'))
		return
	}
	const escape = (value) => {
		const text = value === null || value === undefined ? '' : String(value)
		return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
	}
	const lines = [
		['Month', 'Course', 'Enrollments', 'Completions', 'CEU hours issued'].join(','),
	]
	rows.forEach((row) => {
		lines.push(
			[
				row.period,
				row.course_title || row.course,
				row.enrollments,
				row.completions,
				row.ceu_hours_issued,
			]
				.map(escape)
				.join(','),
		)
	})
	const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
	const link = document.createElement('a')
	link.href = URL.createObjectURL(blob)
	link.download = `ppt4ed-monthly-courses-${fromDate.value}-to-${toDate.value}.csv`
	link.click()
	URL.revokeObjectURL(link.href)
}
</script>
