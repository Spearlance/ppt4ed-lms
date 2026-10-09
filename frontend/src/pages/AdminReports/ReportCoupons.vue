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

		<div class="grid grid-cols-2 gap-3 sm:grid-cols-5">
			<div class="rounded-md border p-3">
				<div class="text-xs text-ink-gray-5">{{ __('Redemptions') }}</div>
				<div class="mt-1 text-xl font-semibold text-ink-gray-9">
					{{ summary.redemptions ?? 0 }}
				</div>
			</div>
			<div class="rounded-md border p-3">
				<div class="text-xs text-ink-gray-5">{{ __('List value') }}</div>
				<div class="mt-1 text-xl font-semibold text-ink-gray-9">
					{{ usd(summary.list_value) }}
				</div>
			</div>
			<div class="rounded-md border p-3">
				<div class="text-xs text-ink-gray-5">{{ __('Discount given') }}</div>
				<div class="mt-1 text-xl font-semibold text-ink-gray-9">
					{{ usd(summary.discount_given) }}
				</div>
			</div>
			<div class="rounded-md border p-3">
				<div class="text-xs text-ink-gray-5">{{ __('Paid after coupon') }}</div>
				<div class="mt-1 text-xl font-semibold text-ink-gray-9">
					{{ usd(summary.net_revenue) }}
				</div>
			</div>
			<div class="rounded-md border p-3">
				<div class="text-xs text-ink-gray-5">{{ __('Comps (100% off)') }}</div>
				<div class="mt-1 text-xl font-semibold text-ink-gray-9">
					{{ summary.comps ?? 0 }}
					<span class="text-sm font-normal text-ink-gray-5">
						· {{ usd(summary.comp_value) }}
					</span>
				</div>
			</div>
		</div>

		<div>
			<h3 class="mb-2 text-base font-semibold text-ink-gray-9">
				{{ __('By code') }}
			</h3>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b text-left text-ink-gray-5">
							<th class="pb-2 pr-4 font-medium">{{ __('Code') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Discount') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Status') }}</th>
							<th class="pb-2 pr-4 text-right font-medium">{{ __('Used in range') }}</th>
							<th class="pb-2 pr-4 text-right font-medium">{{ __('Comps') }}</th>
							<th class="pb-2 pr-4 text-right font-medium">{{ __('List value') }}</th>
							<th class="pb-2 pr-4 text-right font-medium">{{ __('Discount given') }}</th>
							<th class="pb-2 pr-4 text-right font-medium">{{ __('Paid') }}</th>
							<th class="pb-2 text-right font-medium">{{ __('Lifetime / limit') }}</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="row in report.data?.by_code || []" :key="row.coupon" class="border-b last:border-0">
							<td class="py-2 pr-4 font-mono font-medium text-ink-gray-9">{{ row.code }}</td>
							<td class="py-2 pr-4 text-ink-gray-7">{{ row.discount_label }}</td>
							<td class="py-2 pr-4">
								<Badge :theme="codeTheme(row)">{{ codeStatus(row) }}</Badge>
							</td>
							<td class="py-2 pr-4 text-right font-mono text-ink-gray-9">{{ row.redemptions }}</td>
							<td class="py-2 pr-4 text-right text-ink-gray-7">{{ row.comps }}</td>
							<td class="py-2 pr-4 text-right text-ink-gray-7">{{ usd(row.list_value) }}</td>
							<td class="py-2 pr-4 text-right font-mono text-ink-gray-9">{{ usd(row.discount_given) }}</td>
							<td class="py-2 pr-4 text-right font-mono text-ink-gray-9">{{ usd(row.net_revenue) }}</td>
							<td class="py-2 text-right text-ink-gray-7">
								{{ row.lifetime_redemptions || 0 }} / {{ row.usage_limit || '∞' }}
							</td>
						</tr>
						<tr v-if="!report.data?.by_code?.length && !report.loading">
							<td class="py-6 text-center text-ink-gray-5" colspan="9">
								{{ __('No coupons exist yet. Create one under Settings → Coupons.') }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<div>
			<h3 class="mb-2 text-base font-semibold text-ink-gray-9">
				{{ __('By item') }}
			</h3>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b text-left text-ink-gray-5">
							<th class="pb-2 pr-4 font-medium">{{ __('Code') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Item') }}</th>
							<th class="pb-2 pr-4 text-right font-medium">{{ __('Redemptions') }}</th>
							<th class="pb-2 pr-4 text-right font-medium">{{ __('Comps') }}</th>
							<th class="pb-2 pr-4 text-right font-medium">{{ __('Discount given') }}</th>
							<th class="pb-2 text-right font-medium">{{ __('Paid') }}</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="row in report.data?.by_item || []"
							:key="`${row.code}|${row.item}`"
							class="border-b last:border-0"
						>
							<td class="py-2 pr-4 font-mono text-ink-gray-9">{{ row.code }}</td>
							<td class="py-2 pr-4 text-ink-gray-9">
								{{ row.item_title }}
								<span class="text-xs text-ink-gray-5">· {{ itemKind(row.item_type) }}</span>
							</td>
							<td class="py-2 pr-4 text-right font-mono text-ink-gray-9">{{ row.redemptions }}</td>
							<td class="py-2 pr-4 text-right text-ink-gray-7">{{ row.comps }}</td>
							<td class="py-2 pr-4 text-right font-mono text-ink-gray-9">{{ usd(row.discount_given) }}</td>
							<td class="py-2 text-right font-mono text-ink-gray-9">{{ usd(row.net_revenue) }}</td>
						</tr>
						<tr v-if="!report.data?.by_item?.length && !report.loading">
							<td class="py-6 text-center text-ink-gray-5" colspan="6">
								{{ __('No coupon redemptions in this range.') }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<div>
			<h3 class="mb-2 text-base font-semibold text-ink-gray-9">
				{{ __('Recent redemptions') }}
			</h3>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b text-left text-ink-gray-5">
							<th class="pb-2 pr-4 font-medium">{{ __('When') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Member') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Code') }}</th>
							<th class="pb-2 pr-4 font-medium">{{ __('Item') }}</th>
							<th class="pb-2 pr-4 text-right font-medium">{{ __('List') }}</th>
							<th class="pb-2 pr-4 text-right font-medium">{{ __('Discount') }}</th>
							<th class="pb-2 text-right font-medium">{{ __('Paid') }}</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="row in report.data?.recent || []" :key="row.name" class="border-b last:border-0">
							<td class="py-2 pr-4 whitespace-nowrap text-ink-gray-7">
								{{ dayjs(row.creation).format('MMM D, YYYY HH:mm') }}
							</td>
							<td class="py-2 pr-4 text-ink-gray-9">{{ row.member_name || row.member }}</td>
							<td class="py-2 pr-4 font-mono text-ink-gray-9">{{ row.code }}</td>
							<td class="py-2 pr-4 text-ink-gray-7">
								{{ row.item_title }}
								<span class="text-xs text-ink-gray-5">· {{ itemKind(row.item_type) }}</span>
							</td>
							<td class="py-2 pr-4 text-right text-ink-gray-7">{{ usd(row.original_amount) }}</td>
							<td class="py-2 pr-4 text-right font-mono text-ink-gray-9">{{ usd(row.discount_amount) }}</td>
							<td class="py-2 text-right font-mono text-ink-gray-9">
								<Badge v-if="row.is_comp" theme="orange">{{ __('Comp') }}</Badge>
								<template v-else>{{ usd(row.amount) }}</template>
							</td>
						</tr>
						<tr v-if="!report.data?.recent?.length && !report.loading">
							<td class="py-6 text-center text-ink-gray-5" colspan="7">
								{{ __('No coupon redemptions in this range.') }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
			<p class="mt-2 text-xs text-ink-gray-5">
				{{
					__(
						'A comp is a 100% code: the seat was given away and nothing went through Stripe, so it never appears on the Money tab. "Paid" is what Stripe actually charged after the discount; the Money tab shows the same figure.'
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
	url: 'lms.lms.ceu_reports.get_coupon_report',
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
const itemKind = (type) => (type === 'LMS Event' ? __('Event') : __('Course'))

const today = iso(new Date())
const codeStatus = (row) => {
	if (!row.enabled) return __('Disabled')
	if (row.expires_on && String(row.expires_on) < today) return __('Expired')
	if (row.usage_limit && (row.lifetime_redemptions || 0) >= row.usage_limit) return __('Limit reached')
	return __('Active')
}
const codeTheme = (row) => {
	const status = codeStatus(row)
	if (status === __('Active')) return 'green'
	if (status === __('Disabled')) return 'gray'
	return 'orange'
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
		['When', 'Member', 'Code', 'Item type', 'Item', 'List price', 'Discount', 'Paid', 'Comp'].join(','),
	]
	rows.forEach((row) => {
		lines.push(
			[
				row.creation,
				row.member,
				row.code,
				itemKind(row.item_type),
				row.item_title,
				row.original_amount,
				row.discount_amount,
				row.amount,
				row.is_comp ? 'yes' : 'no',
			]
				.map(escape)
				.join(',')
		)
	})
	const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
	const link = document.createElement('a')
	link.href = URL.createObjectURL(blob)
	link.download = `ppt4ed-coupons-${fromDate.value}-to-${toDate.value}.csv`
	link.click()
	URL.revokeObjectURL(link.href)
}
</script>
