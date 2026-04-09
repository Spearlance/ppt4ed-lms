<template>
	<div class="p-5">
		<div v-if="credits.data?.length" class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b text-left text-ink-gray-5">
						<th class="pb-2 pr-4 font-medium">{{ __('Date') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Type') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('User') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Course') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('Hours') }}</th>
						<th class="pb-2 font-medium text-right">{{ __('Balance') }}</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="entry in credits.data"
						:key="entry.name"
						class="border-b last:border-0"
					>
						<td class="py-3 pr-4 text-ink-gray-5">
							{{ dayjs(entry.timestamp).format('MMM D, YYYY h:mm A') }}
						</td>
						<td class="py-3 pr-4">
							<Badge :theme="entry.transaction_type === 'Allocation' ? 'green' : 'blue'">
								{{ entry.transaction_type }}
							</Badge>
						</td>
						<td class="py-3 pr-4 text-ink-gray-7">
							{{ entry.user_name }}
						</td>
						<td class="py-3 pr-4 text-ink-gray-7">
							{{ entry.course || '—' }}
						</td>
						<td class="py-3 pr-4 text-right font-mono"
							:class="entry.hours > 0 ? 'text-green-600' : 'text-ink-gray-7'"
						>
							{{ entry.hours > 0 ? '+' : '' }}{{ entry.hours }}
						</td>
						<td class="py-3 text-right font-mono text-ink-gray-9">
							{{ entry.balance_after }}
						</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div v-else-if="credits.loading" class="text-center py-10 text-ink-gray-5">
			{{ __('Loading...') }}
		</div>
		<div v-else class="text-center py-10 text-ink-gray-5">
			{{ __('No credit activity yet.') }}
		</div>
	</div>
</template>

<script setup>
import { Badge, createResource } from 'frappe-ui'
import dayjs from 'dayjs'

const credits = createResource({
	url: 'lms.lms.ceu_company_dashboard.get_credit_history',
	cache: ['company-credit-history'],
	auto: true,
})
</script>
