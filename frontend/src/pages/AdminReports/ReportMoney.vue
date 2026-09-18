<template>
	<div class="p-5 space-y-6">
		<!-- Controls -->
		<div class="flex flex-wrap items-end gap-3">
			<FormControl
				v-model="fromDate"
				:label="__('From')"
				type="date"
				class="w-40"
			/>
			<FormControl
				v-model="toDate"
				:label="__('To')"
				type="date"
				class="w-40"
			/>
			<div class="flex gap-1 pb-0.5">
				<Button
					v-for="preset in presets"
					:key="preset.label"
					size="sm"
					:variant="activePreset === preset.label ? 'subtle' : 'ghost'"
					@click="applyPreset(preset)"
				>
					{{ __(preset.label) }}
				</Button>
			</div>
			<div class="grow" />
			<Button size="sm" variant="ghost" :loading="sync.loading" @click="runSync">
				{{ __('Sync from Stripe') }}
			</Button>
			<Button size="sm" variant="subtle" @click="downloadCsv">
				{{ __('Export CSV') }}
			</Button>
		</div>

		<!-- Summary -->
		<div v-if="summary.data" class="grid grid-cols-2 gap-4 lg:grid-cols-4">
			<div
				v-for="card in cards"
				:key="card.label"
				class="rounded-lg border border-outline-gray-2 p-4"
			>
				<div class="text-sm text-ink-gray-5">{{ __(card.label) }}</div>
				<div class="mt-1 text-2xl font-semibold text-ink-gray-9">
					{{ card.value }}
				</div>
				<div v-if="card.sub" class="mt-1 text-xs text-ink-gray-5">
					{{ card.sub }}
				</div>
			</div>
		</div>

		<div v-if="summary.data" class="grid gap-6 lg:grid-cols-2">
			<!-- By type -->
			<div>
				<h3 class="mb-2 text-base font-semibold text-ink-gray-9">
					{{ __('Where the money came from') }}
				</h3>
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b text-left text-ink-gray-5">
							<th class="pb-2 pr-4 font-medium">{{ __('Type') }}</th>
							<th class="pb-2 pr-4 font-medium text-right">{{ __('Transactions') }}</th>
							<th class="pb-2 pr-4 font-medium text-right">{{ __('Refunds') }}</th>
							<th class="pb-2 font-medium text-right">{{ __('Net') }}</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="row in summary.data.by_type"
							:key="row.transaction_type"
							class="border-b last:border-0"
						>
							<td class="py-2 pr-4 font-medium text-ink-gray-9">
								{{ row.transaction_type }}
							</td>
							<td class="py-2 pr-4 text-right text-ink-gray-7">{{ row.transactions }}</td>
							<td class="py-2 pr-4 text-right text-ink-gray-7">{{ money(row.refunded) }}</td>
							<td class="py-2 text-right font-mono text-ink-gray-9">{{ money(row.net) }}</td>
						</tr>
						<tr v-if="!summary.data.by_type?.length">
							<td class="py-3 text-ink-gray-5" colspan="4">
								{{ __('No transactions in this range.') }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>

			<!-- By month -->
			<div>
				<h3 class="mb-2 text-base font-semibold text-ink-gray-9">
					{{ __('Month by month') }}
				</h3>
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b text-left text-ink-gray-5">
							<th class="pb-2 pr-4 font-medium">{{ __('Month') }}</th>
							<th class="pb-2 pr-4 font-medium text-right">{{ __('Transactions') }}</th>
							<th class="pb-2 pr-4 font-medium text-right">{{ __('Gross') }}</th>
							<th class="pb-2 font-medium text-right">{{ __('Net') }}</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="row in summary.data.by_month"
							:key="row.period"
							class="border-b last:border-0"
						>
							<td class="py-2 pr-4 font-medium text-ink-gray-9">{{ row.period }}</td>
							<td class="py-2 pr-4 text-right text-ink-gray-7">{{ row.transactions }}</td>
							<td class="py-2 pr-4 text-right text-ink-gray-7">{{ money(row.gross) }}</td>
							<td class="py-2 text-right font-mono text-ink-gray-9">{{ money(row.net) }}</td>
						</tr>
						<tr v-if="!summary.data.by_month?.length">
							<td class="py-3 text-ink-gray-5" colspan="4">
								{{ __('No transactions in this range.') }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<!-- Top sellers -->
		<div v-if="summary.data?.top_items?.length">
			<h3 class="mb-2 text-base font-semibold text-ink-gray-9">
				{{ __('Top sellers') }}
			</h3>
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b text-left text-ink-gray-5">
						<th class="pb-2 pr-4 font-medium">{{ __('Item') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Type') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('Transactions') }}</th>
						<th class="pb-2 font-medium text-right">{{ __('Net') }}</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="row in summary.data.top_items"
						:key="`${row.item_title}-${row.transaction_type}`"
						class="border-b last:border-0"
					>
						<td class="py-2 pr-4 font-medium text-ink-gray-9">{{ row.item_title }}</td>
						<td class="py-2 pr-4 text-ink-gray-5">{{ row.transaction_type }}</td>
						<td class="py-2 pr-4 text-right text-ink-gray-7">{{ row.transactions }}</td>
						<td class="py-2 text-right font-mono text-ink-gray-9">{{ money(row.net) }}</td>
					</tr>
				</tbody>
			</table>
		</div>

		<!-- Transactions -->
		<div>
			<div class="mb-2 flex flex-wrap items-center gap-3">
				<h3 class="text-base font-semibold text-ink-gray-9">
					{{ __('Transactions') }}
				</h3>
				<div class="flex gap-1">
					<Button
						v-for="type in typeFilters"
						:key="type"
						size="sm"
						:variant="transactionType === type ? 'subtle' : 'ghost'"
						@click="transactionType = type"
					>
						{{ __(type) }}
					</Button>
				</div>
				<FormControl
					v-model="search"
					type="text"
					:placeholder="__('Search name, email or item')"
					class="w-64"
				/>
				<span v-if="transactions.data" class="text-sm text-ink-gray-5">
					{{ transactions.data.total_count }} {{ __('transactions') }} ·
					{{ money(transactions.data.total_net) }} {{ __('net') }}
				</span>
			</div>

			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b text-left text-ink-gray-5">
							<th
								v-for="col in columns"
								:key="col.key"
								class="cursor-pointer pb-2 pr-4 font-medium select-none"
								:class="col.align === 'right' ? 'text-right' : ''"
								@click="sortBy(col.key)"
							>
								{{ __(col.label) }}
								<span v-if="sortKey === col.key">{{ sortAsc ? '↑' : '↓' }}</span>
							</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="row in sortedRows"
							:key="row.stripe_id"
							class="cursor-pointer border-b last:border-0 hover:bg-surface-gray-1"
							@click="openMember(row)"
						>
							<td class="py-2 pr-4 text-ink-gray-7">{{ shortDate(row.transaction_date) }}</td>
							<td class="py-2 pr-4 font-medium text-ink-gray-9">
								{{ row.member_full_name || row.customer_email || '—' }}
							</td>
							<td class="py-2 pr-4 text-ink-gray-7">{{ row.item_title || '—' }}</td>
							<td class="py-2 pr-4 text-ink-gray-5">{{ row.transaction_type }}</td>
							<td class="py-2 pr-4 text-right text-ink-gray-7">{{ money(row.gross_amount) }}</td>
							<td class="py-2 pr-4 text-right text-ink-gray-7">
								{{ row.refunded_amount ? money(row.refunded_amount) : '—' }}
							</td>
							<td class="py-2 text-right font-mono text-ink-gray-9">{{ money(row.net_amount) }}</td>
						</tr>
						<tr v-if="!sortedRows.length && !transactions.loading">
							<td class="py-6 text-center text-ink-gray-5" colspan="7">
								{{ __('No transactions match this range and filter.') }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>

			<p class="mt-3 text-xs text-ink-gray-5">
				{{ summary.data?.fee_note || __('Amounts are Stripe charges.') }}
				<span v-if="syncStatus.data?.last_synced">
					{{ __('Last synced from Stripe') }}: {{ syncStatus.data.last_synced }}.
				</span>
				<span v-if="syncStatus.data?.unclassified">
					{{ syncStatus.data.unclassified }}
					{{ __('transactions could not be matched to a course, event or membership and are counted as Other.') }}
				</span>
			</p>
		</div>

		<!-- Member detail -->
		<Dialog
			v-model="showMemberDialog"
			:options="{ title: memberDialogTitle, size: '2xl' }"
		>
			<template #body-content>
				<div v-if="memberDetail.loading" class="py-6 text-center text-ink-gray-5">
					{{ __('Loading...') }}
				</div>
				<div v-else-if="memberDetail.data" class="space-y-5">
					<div class="flex flex-wrap gap-6 text-sm">
						<div>
							<div class="text-ink-gray-5">{{ __('Email') }}</div>
							<div class="font-medium text-ink-gray-9">
								{{ memberDetail.data.member.email }}
							</div>
						</div>
						<div>
							<div class="text-ink-gray-5">{{ __('Lifetime net') }}</div>
							<div class="font-medium text-ink-gray-9">
								{{ money(memberDetail.data.lifetime_net) }}
							</div>
						</div>
						<div>
							<div class="text-ink-gray-5">{{ __('Transactions') }}</div>
							<div class="font-medium text-ink-gray-9">
								{{ memberDetail.data.lifetime_transactions }}
							</div>
						</div>
					</div>

					<div v-if="memberDetail.data.memberships?.length">
						<h4 class="mb-1 font-semibold text-ink-gray-9">{{ __('Membership') }}</h4>
						<div
							v-for="m in memberDetail.data.memberships"
							:key="m.name"
							class="text-sm text-ink-gray-7"
						>
							{{ m.plan }} · {{ m.status }} · {{ m.credit_balance }} {{ __('credit hours') }}
						</div>
					</div>

					<div>
						<h4 class="mb-1 font-semibold text-ink-gray-9">{{ __('Purchases') }}</h4>
						<table class="w-full text-sm">
							<tbody>
								<tr
									v-for="t in memberDetail.data.transactions"
									:key="t.stripe_id"
									class="border-b last:border-0"
								>
									<td class="py-1.5 pr-3 text-ink-gray-7">{{ shortDate(t.transaction_date) }}</td>
									<td class="py-1.5 pr-3 text-ink-gray-9">{{ t.item_title || t.transaction_type }}</td>
									<td class="py-1.5 text-right font-mono text-ink-gray-9">{{ money(t.net_amount) }}</td>
								</tr>
								<tr v-if="!memberDetail.data.transactions?.length">
									<td class="py-2 text-ink-gray-5">{{ __('No purchases recorded.') }}</td>
								</tr>
							</tbody>
						</table>
					</div>

					<div>
						<h4 class="mb-1 font-semibold text-ink-gray-9">{{ __('Enrolled in') }}</h4>
						<table class="w-full text-sm">
							<tbody>
								<tr
									v-for="e in memberDetail.data.enrollments"
									:key="e.course"
									class="border-b last:border-0"
								>
									<td class="py-1.5 pr-3 text-ink-gray-9">{{ e.course_title || e.course }}</td>
									<td class="py-1.5 pr-3 text-ink-gray-5">{{ e.credit_source || '—' }}</td>
									<td class="py-1.5 text-right text-ink-gray-7">{{ e.progress || 0 }}%</td>
								</tr>
								<tr v-if="!memberDetail.data.enrollments?.length">
									<td class="py-2 text-ink-gray-5">{{ __('No enrollments.') }}</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, Dialog, FormControl, createResource, toast } from 'frappe-ui'

const columns = [
	{ key: 'transaction_date', label: 'Date' },
	{ key: 'member_full_name', label: 'Member' },
	{ key: 'item_title', label: 'Item' },
	{ key: 'transaction_type', label: 'Type' },
	{ key: 'gross_amount', label: 'Gross', align: 'right' },
	{ key: 'refunded_amount', label: 'Refunded', align: 'right' },
	{ key: 'net_amount', label: 'Net', align: 'right' },
]

const typeFilters = ['All', 'Course', 'Event', 'Membership', 'Other']

const iso = (d) => d.toISOString().slice(0, 10)

const startOfMonth = (offset = 0) => {
	const d = new Date()
	return new Date(d.getFullYear(), d.getMonth() + offset, 1)
}
const endOfMonth = (offset = 0) => {
	const d = new Date()
	return new Date(d.getFullYear(), d.getMonth() + offset + 1, 0)
}
const daysAgo = (n) => {
	const d = new Date()
	d.setDate(d.getDate() - n)
	return d
}

const presets = [
	{ label: 'This month', from: () => startOfMonth(), to: () => new Date() },
	{ label: 'Last month', from: () => startOfMonth(-1), to: () => endOfMonth(-1) },
	{ label: 'Last 90 days', from: () => daysAgo(90), to: () => new Date() },
	{
		label: 'This year',
		from: () => new Date(new Date().getFullYear(), 0, 1),
		to: () => new Date(),
	},
	{ label: 'All time', from: () => new Date(2020, 0, 1), to: () => new Date() },
]

const activePreset = ref('This month')
const fromDate = ref(iso(startOfMonth()))
const toDate = ref(iso(new Date()))
const transactionType = ref('All')
const search = ref('')
const sortKey = ref('transaction_date')
const sortAsc = ref(false)

const applyPreset = (preset) => {
	activePreset.value = preset.label
	fromDate.value = iso(preset.from())
	toDate.value = iso(preset.to())
}

const summary = createResource({
	url: 'lms.lms.ceu_reports.get_money_summary',
	makeParams: () => ({ from_date: fromDate.value, to_date: toDate.value }),
	auto: true,
})

const transactions = createResource({
	url: 'lms.lms.ceu_reports.get_transactions_report',
	makeParams: () => ({
		from_date: fromDate.value,
		to_date: toDate.value,
		transaction_type: transactionType.value,
		search: search.value,
		limit: 500,
	}),
	auto: true,
})

const syncStatus = createResource({
	url: 'lms.lms.ceu_transactions.get_sync_status',
	auto: true,
})

const sync = createResource({
	url: 'lms.lms.ceu_transactions.sync_now',
	makeParams: () => ({ since_days: 3650 }),
	onSuccess: () => {
		toast.success(__('Stripe sync queued. Refresh in a minute to see new transactions.'))
	},
	onError: () => {
		toast.error(__('Could not queue the Stripe sync.'))
	},
})

const runSync = () => sync.submit()

let reloadTimer = null
watch([fromDate, toDate, transactionType, search], () => {
	clearTimeout(reloadTimer)
	reloadTimer = setTimeout(() => {
		summary.reload()
		transactions.reload()
	}, 250)
})

const money = (value) => {
	const number = Number(value || 0)
	return number.toLocaleString(undefined, {
		style: 'currency',
		currency: 'USD',
		maximumFractionDigits: 2,
	})
}

const shortDate = (value) => (value ? String(value).slice(0, 10) : '—')

const pct = (value) => {
	if (value === null || value === undefined) return null
	const sign = value > 0 ? '+' : ''
	return `${sign}${value}% ${__('vs previous period')}`
}

const cards = computed(() => {
	const data = summary.data
	if (!data) return []
	const totals = data.totals || {}
	return [
		{
			label: 'Net revenue',
			value: money(totals.net),
			sub: pct(data.change?.net_pct),
		},
		{ label: 'Gross charged', value: money(totals.gross) },
		{ label: 'Refunded', value: money(totals.refunded) },
		{
			label: 'Transactions',
			value: totals.transactions || 0,
			sub: pct(data.change?.transactions_pct),
		},
	]
})

const sortedRows = computed(() => {
	const rows = [...(transactions.data?.rows || [])]
	const key = sortKey.value
	rows.sort((a, b) => {
		const x = a[key] ?? ''
		const y = b[key] ?? ''
		if (typeof x === 'number' && typeof y === 'number') {
			return sortAsc.value ? x - y : y - x
		}
		return sortAsc.value
			? String(x).localeCompare(String(y))
			: String(y).localeCompare(String(x))
	})
	return rows
})

const sortBy = (key) => {
	if (sortKey.value === key) {
		sortAsc.value = !sortAsc.value
	} else {
		sortKey.value = key
		sortAsc.value = false
	}
}

const downloadCsv = () => {
	const rows = sortedRows.value
	if (!rows.length) {
		toast.error(__('Nothing to export for this range.'))
		return
	}
	const header = [
		'Date',
		'Member',
		'Email',
		'Item',
		'Type',
		'Gross',
		'Refunded',
		'Net',
		'Currency',
		'Stripe ID',
	]
	const escape = (value) => {
		const text = value === null || value === undefined ? '' : String(value)
		return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
	}
	const lines = [header.join(',')]
	rows.forEach((row) => {
		lines.push(
			[
				shortDate(row.transaction_date),
				row.member_full_name,
				row.customer_email,
				row.item_title,
				row.transaction_type,
				row.gross_amount,
				row.refunded_amount,
				row.net_amount,
				row.currency,
				row.stripe_id,
			]
				.map(escape)
				.join(','),
		)
	})

	const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
	const link = document.createElement('a')
	link.href = URL.createObjectURL(blob)
	link.download = `ppt4ed-transactions-${fromDate.value}-to-${toDate.value}.csv`
	link.click()
	URL.revokeObjectURL(link.href)
}

const showMemberDialog = ref(false)
const selectedMember = ref(null)

const memberDetail = createResource({
	url: 'lms.lms.ceu_reports.get_member_purchase_detail',
	makeParams: () => ({ member: selectedMember.value }),
})

const memberDialogTitle = computed(() =>
	memberDetail.data?.member?.full_name
		? `${memberDetail.data.member.full_name}`
		: __('Member'),
)

const openMember = (row) => {
	if (!row.member) {
		toast.error(__('This transaction is not linked to a member account.'))
		return
	}
	selectedMember.value = row.member
	showMemberDialog.value = true
	memberDetail.fetch()
}
</script>
