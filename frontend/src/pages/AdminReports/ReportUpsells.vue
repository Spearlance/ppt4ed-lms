<template>
	<div class="space-y-6 p-5">
		<div class="flex flex-wrap items-end gap-3">
			<FormControl v-model="fromDate" :label="__('From')" type="date" class="w-40" />
			<FormControl v-model="toDate" :label="__('To')" type="date" class="w-40" />
			<div class="grow" />
			<Button size="sm" variant="subtle" @click="downloadCsv">
				{{ __('Export CSV') }}
			</Button>
		</div>

		<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
			<div class="rounded-md border p-3">
				<div class="text-xs text-ink-gray-5">{{ __('Course orders') }}</div>
				<div class="mt-1 text-xl font-semibold text-ink-gray-9">
					{{ summary.orders ?? 0 }}
				</div>
			</div>
			<div class="rounded-md border p-3">
				<div class="text-xs text-ink-gray-5">{{ __('Average order value') }}</div>
				<div class="mt-1 text-xl font-semibold text-ink-gray-9">
					{{ usd(summary.average_order_value) }}
				</div>
			</div>
			<div class="rounded-md border p-3">
				<div class="text-xs text-ink-gray-5">{{ __('Upsell revenue') }}</div>
				<div class="mt-1 text-xl font-semibold text-ink-gray-9">
					{{ usd(summary.upsell_revenue) }}
				</div>
			</div>
			<div class="rounded-md border p-3">
				<div class="text-xs text-ink-gray-5">{{ __('Share of course revenue') }}</div>
				<div class="mt-1 text-xl font-semibold text-ink-gray-9">
					{{ summary.upsell_share_pct ?? 0 }}%
				</div>
			</div>
		</div>

		<div>
			<h3 class="mb-2 text-base font-semibold text-ink-gray-9">
				{{ __('By offer type') }}
			</h3>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b text-left text-ink-gray-5">
							<th class="pb-2 pr-4 font-medium">{{ __('Type') }}</th>
							<th class="pb-2 pr-4 text-right font-medium">{{ __('Offered') }}</th>
							<th class="pb-2 pr-4 text-right font-medium">{{ __('Paid') }}</th>
							<th class="pb-2 pr-4 text-right font-medium">{{ __('Declined') }}</th>
							<th class="pb-2 pr-4 text-right font-medium">{{ __('Fell back') }}</th>
							<th class="pb-2 pr-4 text-right font-medium">{{ __('Conversion') }}</th>
							<th class="pb-2 text-right font-medium">{{ __('Revenue') }}</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="row in report.data?.by_type || []" :key="row.upsell_type" class="border-b last:border-0">
							<td class="py-2 pr-4 font-medium text-ink-gray-9">{{ row.upsell_type }}</td>
							<td class="py-2 pr-4 text-right text-ink-gray-7">{{ row.offered }}</td>
							<td class="py-2 pr-4 text-right font-mono text-ink-gray-9">{{ row.paid }}</td>
							<td class="py-2 pr-4 text-right text-ink-gray-7">{{ row.declined }}</td>
							<td class="py-2 pr-4 text-right text-ink-gray-7">{{ row.fell_back }}</td>
							<td class="py-2 pr-4 text-right text-ink-gray-7">{{ row.conversion_pct }}%</td>
							<td class="py-2 text-right font-mono text-ink-gray-9">{{ usd(row.revenue) }}</td>
						</tr>
						<tr v-if="!report.data?.by_type?.length && !report.loading">
							<td class="py-6 text-center text-ink-gray-5" colspan="7">
								{{ __('No upsell offers in this range.') }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<div>
			<h3 class="mb-2 text-base font-semibold text-ink-gray-9">
				{{ __('By course') }}
			</h3>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b text-left text-ink-gray-5">
							<th class="pb-2 pr-4 font-medium">{{ __('Upsell course') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Offered on') }}</th>
							<th class="pb-2 pr-4 text-right font-medium">{{ __('Offered') }}</th>
							<th class="pb-2 pr-4 text-right font-medium">{{ __('Paid') }}</th>
							<th class="pb-2 pr-4 text-right font-medium">{{ __('Conversion') }}</th>
							<th class="pb-2 text-right font-medium">{{ __('Revenue') }}</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="row in report.data?.by_course || []"
							:key="`${row.upsell_course}|${row.original_course}`"
							class="border-b last:border-0"
						>
							<td class="py-2 pr-4 font-medium text-ink-gray-9">
								{{ row.upsell_title || row.upsell_course }}
							</td>
							<td class="py-2 pr-4 text-ink-gray-7">
								{{ row.original_title || row.original_course }}
							</td>
							<td class="py-2 pr-4 text-right text-ink-gray-7">{{ row.offered }}</td>
							<td class="py-2 pr-4 text-right font-mono text-ink-gray-9">{{ row.paid }}</td>
							<td class="py-2 pr-4 text-right text-ink-gray-7">{{ row.conversion_pct }}%</td>
							<td class="py-2 text-right font-mono text-ink-gray-9">{{ usd(row.revenue) }}</td>
						</tr>
						<tr v-if="!report.data?.by_course?.length && !report.loading">
							<td class="py-6 text-center text-ink-gray-5" colspan="6">
								{{ __('No upsell offers in this range.') }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<div>
			<h3 class="mb-2 text-base font-semibold text-ink-gray-9">
				{{ __('Recent offers') }}
			</h3>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b text-left text-ink-gray-5">
							<th class="pb-2 pr-4 font-medium">{{ __('When') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Member') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Type') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Upsell course') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Status') }}</th>
							<th class="pb-2 text-right font-medium">{{ __('Offer price') }}</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="row in report.data?.recent || []" :key="row.name" class="border-b last:border-0">
							<td class="py-2 pr-4 whitespace-nowrap text-ink-gray-7">
								{{ dayjs(row.creation).format('MMM D, YYYY HH:mm') }}
							</td>
							<td class="py-2 pr-4 text-ink-gray-9">{{ row.member_name || row.member }}</td>
							<td class="py-2 pr-4 text-ink-gray-7">{{ row.upsell_type }}</td>
							<td class="py-2 pr-4 text-ink-gray-7">{{ row.upsell_title || row.upsell_course }}</td>
							<td class="py-2 pr-4">
								<Badge :theme="statusTheme(row.status)" :title="row.error || ''">
									{{ row.status }}
								</Badge>
							</td>
							<td class="py-2 text-right font-mono text-ink-gray-9">{{ usd(row.offer_price) }}</td>
						</tr>
						<tr v-if="!report.data?.recent?.length && !report.loading">
							<td class="py-6 text-center text-ink-gray-5" colspan="6">
								{{ __('No upsell offers in this range.') }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
			<p class="mt-2 text-xs text-ink-gray-5">
				{{
					__(
						'Order bumps are the add-on checkbox next to Buy this course. Post-purchase offers are the one-click page after payment. Turn each on in CEU Stripe Settings; the upsell for a course is its first Related Course.'
					)
				}}
			</p>
		</div>
	</div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Badge, Button, FormControl, createResource, toast } from 'frappe-ui'
import dayjs from 'dayjs'

const iso = (d) => d.toISOString().slice(0, 10)

const monthsAgo = (n) => {
	const d = new Date()
	d.setMonth(d.getMonth() - n)
	return d
}

const fromDate = ref(iso(monthsAgo(12)))
const toDate = ref(iso(new Date()))

const report = createResource({
	url: 'lms.lms.ceu_reports.get_upsell_report',
	makeParams: () => ({ from_date: fromDate.value, to_date: toDate.value }),
	auto: true,
})

const summary = computed(() => report.data?.summary || {})

let reloadTimer = null
watch([fromDate, toDate], () => {
	clearTimeout(reloadTimer)
	reloadTimer = setTimeout(() => report.reload(), 250)
})

const usd = (value) => `$${Number(value || 0).toFixed(2)}`

const statusTheme = (status) => {
	if (status === 'Paid') return 'green'
	if (status === 'Declined' || status === 'Failed') return 'red'
	if (status === 'Checkout' || status === 'Charging') return 'orange'
	return 'gray'
}

const downloadCsv = () => {
	const rows = report.data?.recent || []
	if (!rows.length) {
		toast.error(__('Nothing to export for this range.'))
		return
	}
	const escape = (value) => {
		const text = value === null || value === undefined ? '' : String(value)
		return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
	}
	const lines = [
		['When', 'Member', 'Type', 'Original course', 'Upsell course', 'Status', 'List price', 'Offer price', 'Error'].join(','),
	]
	rows.forEach((row) => {
		lines.push(
			[
				row.creation,
				row.member,
				row.upsell_type,
				row.original_title || row.original_course,
				row.upsell_title || row.upsell_course,
				row.status,
				row.list_price,
				row.offer_price,
				row.error,
			]
				.map(escape)
				.join(',')
		)
	})
	const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
	const link = document.createElement('a')
	link.href = URL.createObjectURL(blob)
	link.download = `ppt4ed-upsells-${fromDate.value}-to-${toDate.value}.csv`
	link.click()
	URL.revokeObjectURL(link.href)
}
</script>
