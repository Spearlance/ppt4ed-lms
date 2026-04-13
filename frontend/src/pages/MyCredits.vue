<template>
	<div>
		<header
			class="sticky top-0 z-10 border-b flex items-center justify-between bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs
				:items="[
					{ label: __('My Credits'), route: { name: 'MyCredits' } },
				]"
			/>
		</header>
		<div v-if="credits.data" class="px-5 pt-4">
			<div class="flex items-center justify-between mb-6">
				<div>
					<h2 class="text-xl font-semibold text-ink-gray-9">
						{{ credits.data.company_name }}
					</h2>
					<div class="text-3xl font-bold text-ink-gray-9 mt-1">
						{{ credits.data.credit_balance }}
						<span class="text-base font-normal text-ink-gray-5">
							{{ __('CEU hours available') }}
						</span>
					</div>
				</div>
				<Badge
					v-if="credits.data.membership_status"
					:theme="credits.data.membership_status === 'Active' ? 'green' : 'orange'"
				>
					{{ credits.data.membership_status }}
				</Badge>
			</div>

			<div>
				<h3 class="text-lg font-semibold text-ink-gray-9 mb-3">
					{{ __('My Usage') }}
				</h3>
				<div v-if="credits.data.my_transactions?.length" class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b text-left text-ink-gray-5">
								<th class="pb-2 pr-4 font-medium">{{ __('Date') }}</th>
								<th class="pb-2 pr-4 font-medium">{{ __('Type') }}</th>
								<th class="pb-2 pr-4 font-medium">{{ __('Course') }}</th>
								<th class="pb-2 pr-4 font-medium text-right">{{ __('Hours') }}</th>
								<th class="pb-2 font-medium text-right">{{ __('Balance') }}</th>
							</tr>
						</thead>
						<tbody>
							<tr
								v-for="entry in credits.data.my_transactions"
								:key="entry.name"
								class="border-b last:border-0"
							>
								<td class="py-3 pr-4 text-ink-gray-5">
									{{ dayjs(entry.timestamp).format('MMM D, YYYY h:mm A') }}
								</td>
								<td class="py-3 pr-4">
									<Badge
										:theme="entry.transaction_type === 'Allocation' ? 'green' : 'blue'"
									>
										{{ entry.transaction_type }}
									</Badge>
								</td>
								<td class="py-3 pr-4 text-ink-gray-7">
									{{ entry.course_title || '—' }}
								</td>
								<td
									class="py-3 pr-4 text-right font-mono"
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
				<div v-else class="text-center py-10 text-ink-gray-5">
					{{ __('No credit usage yet.') }}
				</div>
			</div>
		</div>
		<div v-else-if="credits.loading" class="flex justify-center py-20">
			<p class="text-ink-gray-5">{{ __('Loading...') }}</p>
		</div>
	</div>
</template>

<script setup>
import { Badge, Breadcrumbs, createResource, usePageMeta } from 'frappe-ui'
import dayjs from 'dayjs'

usePageMeta({ title: 'My Credits' })

const credits = createResource({
	url: 'lms.lms.ceu_company_dashboard.get_my_company_credits',
	cache: ['my-company-credits'],
	auto: true,
})
</script>
