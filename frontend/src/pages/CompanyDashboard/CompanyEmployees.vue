<template>
	<div class="p-5">
		<div v-if="members.data?.length" class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b text-left text-ink-gray-5">
						<th class="pb-2 pr-4 font-medium">{{ __('Name') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Email') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Enrollments') }}</th>
						<th class="pb-2 font-medium">{{ __('Last Active') }}</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="member in members.data"
						:key="member.user"
						class="border-b last:border-0"
					>
						<td class="py-3 pr-4 font-medium text-ink-gray-9">
							{{ member.full_name }}
						</td>
						<td class="py-3 pr-4 text-ink-gray-7">
							{{ member.email }}
						</td>
						<td class="py-3 pr-4 text-ink-gray-7">
							{{ member.enrollment_count }}
						</td>
						<td class="py-3 text-ink-gray-5">
							{{ member.last_active ? dayjs(member.last_active).fromNow() : __('Never') }}
						</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div v-else-if="members.loading" class="text-center py-10 text-ink-gray-5">
			{{ __('Loading...') }}
		</div>
		<div v-else class="text-center py-10 text-ink-gray-5">
			{{ __('No members yet. Send invites to get started.') }}
		</div>
	</div>
</template>

<script setup>
import { createResource } from 'frappe-ui'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'

dayjs.extend(relativeTime)

const members = createResource({
	url: 'lms.lms.ceu_company_dashboard.get_company_members',
	cache: ['company-members'],
	auto: true,
})
</script>
