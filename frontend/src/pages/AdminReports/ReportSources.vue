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

		<div>
			<h3 class="mb-2 text-base font-semibold text-ink-gray-9">
				{{ __('Where signups came from') }}
			</h3>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b text-left text-ink-gray-5">
							<th class="pb-2 pr-4 font-medium">{{ __('Source') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Medium') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Campaign') }}</th>
							<th class="pb-2 pr-4 font-medium text-right">{{ __('New accounts') }}</th>
							<th class="pb-2 pr-4 font-medium text-right">{{ __('Course enrollments') }}</th>
							<th class="pb-2 pr-4 font-medium text-right">{{ __('Event registrations') }}</th>
							<th class="pb-2 font-medium text-right">{{ __('Resource claims') }}</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="row in report.data?.sources || []"
							:key="rowKey(row)"
							class="border-b last:border-0"
						>
							<td class="py-2 pr-4 font-medium text-ink-gray-9">{{ sourceLabel(row) }}</td>
							<td class="py-2 pr-4 text-ink-gray-7">{{ mediumLabel(row) }}</td>
							<td class="py-2 pr-4 text-ink-gray-7">{{ row.traffic_campaign || '—' }}</td>
							<td class="py-2 pr-4 text-right text-ink-gray-7">{{ row.signups }}</td>
							<td class="py-2 pr-4 text-right font-mono text-ink-gray-9">
								{{ row.course_enrollments }}
							</td>
							<td class="py-2 pr-4 text-right font-mono text-ink-gray-9">
								{{ row.event_registrations }}
							</td>
							<td class="py-2 text-right text-ink-gray-7">{{ row.resource_claims }}</td>
						</tr>
						<tr v-if="!report.data?.sources?.length && !report.loading">
							<td class="py-6 text-center text-ink-gray-5" colspan="7">
								{{ __('No signups or enrollments in this range.') }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<div>
			<h3 class="mb-2 text-base font-semibold text-ink-gray-9">
				{{ __('Course by source') }}
			</h3>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b text-left text-ink-gray-5">
							<th class="pb-2 pr-4 font-medium">{{ __('Course') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Source') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Medium') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Campaign') }}</th>
							<th class="pb-2 font-medium text-right">{{ __('Enrollments') }}</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="row in report.data?.by_course || []"
							:key="`${row.course}|${rowKey(row)}`"
							class="border-b last:border-0"
						>
							<td class="py-2 pr-4 font-medium text-ink-gray-9">
								{{ row.course_title || row.course }}
							</td>
							<td class="py-2 pr-4 text-ink-gray-7">{{ sourceLabel(row) }}</td>
							<td class="py-2 pr-4 text-ink-gray-7">{{ mediumLabel(row) }}</td>
							<td class="py-2 pr-4 text-ink-gray-7">{{ row.traffic_campaign || '—' }}</td>
							<td class="py-2 text-right font-mono text-ink-gray-9">{{ row.enrollments }}</td>
						</tr>
						<tr v-if="!report.data?.by_course?.length && !report.loading">
							<td class="py-6 text-center text-ink-gray-5" colspan="5">
								{{ __('No enrollments in this range.') }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<div>
			<h3 class="mb-2 text-base font-semibold text-ink-gray-9">
				{{ __('Event by source') }}
			</h3>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b text-left text-ink-gray-5">
							<th class="pb-2 pr-4 font-medium">{{ __('Event') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Source') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Medium') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Campaign') }}</th>
							<th class="pb-2 font-medium text-right">{{ __('Registrations') }}</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="row in report.data?.by_event || []"
							:key="`${row.event}|${rowKey(row)}`"
							class="border-b last:border-0"
						>
							<td class="py-2 pr-4 font-medium text-ink-gray-9">
								{{ row.event_title || row.event }}
							</td>
							<td class="py-2 pr-4 text-ink-gray-7">{{ sourceLabel(row) }}</td>
							<td class="py-2 pr-4 text-ink-gray-7">{{ mediumLabel(row) }}</td>
							<td class="py-2 pr-4 text-ink-gray-7">{{ row.traffic_campaign || '—' }}</td>
							<td class="py-2 text-right font-mono text-ink-gray-9">{{ row.registrations }}</td>
						</tr>
						<tr v-if="!report.data?.by_event?.length && !report.loading">
							<td class="py-6 text-center text-ink-gray-5" colspan="5">
								{{ __('No event registrations in this range.') }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
			<p class="mt-3 text-xs text-ink-gray-5">
				{{
					__(
						'Direct means the visitor arrived with no tagged link and no referring site. Not tracked means the record was created before tracking started, or by an admin rather than by the member.',
					)
				}}
			</p>
			<p class="mt-1 text-xs text-ink-gray-5">
				{{ __('To label a link you share, add UTM tags to it, for example:') }}
				<code>?utm_source=newsletter&amp;utm_medium=email&amp;utm_campaign=fall-2026</code>
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

const report = createResource({
	url: 'lms.lms.ceu_reports.get_traffic_source_report',
	makeParams: () => ({ from_date: fromDate.value, to_date: toDate.value }),
	auto: true,
})

let reloadTimer = null
watch([fromDate, toDate], () => {
	clearTimeout(reloadTimer)
	reloadTimer = setTimeout(() => report.reload(), 250)
})

const rowKey = (row) =>
	`${row.traffic_source}|${row.traffic_medium}|${row.traffic_campaign}`

const sourceLabel = (row) => {
	if (row.traffic_source === 'not tracked') return __('Not tracked')
	if (row.traffic_source === 'direct') return __('Direct')
	return row.traffic_source
}

const mediumLabel = (row) =>
	!row.traffic_medium || row.traffic_medium === 'none' ? '—' : row.traffic_medium

const downloadCsv = () => {
	const courses = (report.data?.by_course || []).map((row) => ({
		type: 'Course',
		title: row.course_title || row.course,
		...row,
		count: row.enrollments,
	}))
	const events = (report.data?.by_event || []).map((row) => ({
		type: 'Event',
		title: row.event_title || row.event,
		...row,
		count: row.registrations,
	}))
	const rows = [...courses, ...events]
	if (!rows.length) {
		toast.error(__('Nothing to export for this range.'))
		return
	}
	const escape = (value) => {
		const text = value === null || value === undefined ? '' : String(value)
		return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
	}
	const lines = [['Type', 'Title', 'Source', 'Medium', 'Campaign', 'Count'].join(',')]
	rows.forEach((row) => {
		lines.push(
			[
				row.type,
				row.title,
				row.traffic_source,
				row.traffic_medium,
				row.traffic_campaign,
				row.count,
			]
				.map(escape)
				.join(','),
		)
	})
	const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
	const link = document.createElement('a')
	link.href = URL.createObjectURL(blob)
	link.download = `ppt4ed-sources-${fromDate.value}-to-${toDate.value}.csv`
	link.click()
	URL.revokeObjectURL(link.href)
}
</script>
