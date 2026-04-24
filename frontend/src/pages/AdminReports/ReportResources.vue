<template>
	<div class="p-5">
		<div v-if="resources.data?.length" class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b text-left text-ink-gray-5">
						<th class="pb-2 pr-4 font-medium w-8"></th>
						<th class="pb-2 pr-4 font-medium">{{ __('Resource') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Type') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Audience') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('Claims') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Last Claim') }}</th>
						<th class="pb-2 font-medium">{{ __('Status') }}</th>
					</tr>
				</thead>
				<tbody>
					<template v-for="row in resources.data" :key="row.resource">
						<tr
							class="border-b last:border-0 hover:bg-surface-gray-1 cursor-pointer"
							@click="toggle(row.resource)"
						>
							<td class="py-3 pr-4 text-ink-gray-5">
								<ChevronDown
									v-if="expanded === row.resource"
									class="w-4 h-4 stroke-1.5"
								/>
								<ChevronRight v-else class="w-4 h-4 stroke-1.5" />
							</td>
							<td class="py-3 pr-4 font-medium text-ink-gray-9">
								<router-link
									:to="{ name: 'ResourceDetail', params: { resourceName: row.resource } }"
									class="hover:underline"
									@click.stop
								>
									{{ row.resource_title }}
								</router-link>
							</td>
							<td class="py-3 pr-4 text-ink-gray-7">{{ row.resource_type || '—' }}</td>
							<td class="py-3 pr-4 text-ink-gray-7">{{ row.audience || '—' }}</td>
							<td class="py-3 pr-4 text-right font-mono text-ink-gray-9">
								{{ row.claim_count }}
							</td>
							<td class="py-3 pr-4 text-ink-gray-5">
								{{ row.last_claim_on ? formatDate(row.last_claim_on) : '—' }}
							</td>
							<td class="py-3">
								<Badge :theme="row.published ? 'green' : 'gray'">
									{{ row.published ? __('Published') : __('Draft') }}
								</Badge>
							</td>
						</tr>
						<tr v-if="expanded === row.resource" class="border-b last:border-0 bg-surface-gray-1">
							<td></td>
							<td colspan="6" class="py-3 pr-4">
								<div
									v-if="claimers.loading && claimers.params?.resource === row.resource"
									class="text-ink-gray-5 text-sm py-2"
								>
									{{ __('Loading...') }}
								</div>
								<div
									v-else-if="!claimers.data?.length"
									class="text-ink-gray-5 text-sm py-2"
								>
									{{ __('No claims yet.') }}
								</div>
								<table v-else class="w-full text-sm">
									<thead>
										<tr class="text-left text-ink-gray-5">
											<th class="pb-1 pr-4 font-medium">{{ __('Member') }}</th>
											<th class="pb-1 pr-4 font-medium">{{ __('Email') }}</th>
											<th class="pb-1 pr-4 font-medium">{{ __('Claimed On') }}</th>
											<th class="pb-1 font-medium text-right">{{ __('Progress') }}</th>
										</tr>
									</thead>
									<tbody>
										<tr
											v-for="c in claimers.data"
											:key="c.member"
											class="border-t border-outline-gray-2"
										>
											<td class="py-2 pr-4 text-ink-gray-9">
												{{ c.member_name || c.member }}
											</td>
											<td class="py-2 pr-4 text-ink-gray-7">{{ c.member_email || '—' }}</td>
											<td class="py-2 pr-4 text-ink-gray-5">{{ formatDate(c.claimed_on) }}</td>
											<td class="py-2 text-right font-mono text-ink-gray-7">
												{{ c.progress ? `${Math.round(c.progress)}%` : '—' }}
											</td>
										</tr>
									</tbody>
								</table>
							</td>
						</tr>
					</template>
				</tbody>
			</table>
		</div>
		<div v-else-if="resources.loading" class="text-center py-10 text-ink-gray-5">
			{{ __('Loading...') }}
		</div>
		<div v-else class="text-center py-10 text-ink-gray-5">
			{{ __('No resource data yet.') }}
		</div>
	</div>
</template>

<script setup>
import { Badge, createResource } from 'frappe-ui'
import { ref } from 'vue'
import { ChevronDown, ChevronRight } from 'lucide-vue-next'

const expanded = ref(null)

const resources = createResource({
	url: 'lms.lms.ceu_reports.get_resources_report',
	cache: ['report-resources'],
	auto: true,
})

const claimers = createResource({
	url: 'lms.lms.ceu_reports.get_resource_claimers',
	makeParams(values) {
		return { resource: values?.resource }
	},
})

const toggle = (resource) => {
	if (expanded.value === resource) {
		expanded.value = null
		return
	}
	expanded.value = resource
	claimers.submit({ resource })
}

const formatDate = (value) => {
	if (!value) return '—'
	const d = new Date(value)
	if (isNaN(d.getTime())) return value
	return d.toLocaleDateString(undefined, {
		year: 'numeric',
		month: 'short',
		day: 'numeric',
	})
}
</script>
