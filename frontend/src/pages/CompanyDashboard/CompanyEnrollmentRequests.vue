<template>
	<div class="p-5">
		<div v-if="requests.data?.length" class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b text-left text-ink-gray-5">
						<th class="pb-2 pr-4 font-medium">{{ __('Employee') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Course') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Status') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Requested') }}</th>
						<th class="pb-2 font-medium">{{ __('Actions') }}</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="req in requests.data"
						:key="req.name"
						class="border-b last:border-0"
					>
						<td class="py-3 pr-4 text-ink-gray-9 font-medium">
							{{ req.user_name }}
						</td>
						<td class="py-3 pr-4 text-ink-gray-7">
							{{ req.course_title }}
						</td>
						<td class="py-3 pr-4">
							<Badge :theme="statusTheme(req.status)">
								{{ req.status }}
							</Badge>
						</td>
						<td class="py-3 pr-4 text-ink-gray-5">
							{{ dayjs(req.creation).fromNow() }}
						</td>
						<td class="py-3">
							<div v-if="req.status === 'Pending'" class="flex gap-2">
								<Button
									variant="solid"
									theme="green"
									size="sm"
									:loading="approveRequest.loading"
									@click="handleApprove(req.name)"
								>
									{{ __('Approve') }}
								</Button>
								<Button
									variant="subtle"
									theme="red"
									size="sm"
									:loading="denyRequest.loading"
									@click="handleDeny(req.name)"
								>
									{{ __('Deny') }}
								</Button>
							</div>
							<span v-else-if="req.reviewed_by" class="text-ink-gray-5 text-xs">
								{{ __('by') }} {{ req.reviewed_by }}
							</span>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div v-else-if="requests.loading" class="text-center py-10 text-ink-gray-5">
			{{ __('Loading...') }}
		</div>
		<div v-else class="text-center py-10 text-ink-gray-5">
			{{ __('No enrollment requests.') }}
		</div>
	</div>
</template>

<script setup>
import { Badge, Button, createResource } from 'frappe-ui'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'

dayjs.extend(relativeTime)

const requests = createResource({
	url: 'lms.lms.ceu_company_dashboard.get_enrollment_requests',
	cache: ['company-enrollment-requests'],
	auto: true,
})

const approveRequest = createResource({
	url: 'lms.lms.ceu_enrollment.approve_enrollment_request',
	onSuccess() {
		requests.reload()
	},
})

const denyRequest = createResource({
	url: 'lms.lms.ceu_enrollment.deny_enrollment_request',
	onSuccess() {
		requests.reload()
	},
})

const handleApprove = (requestName) => {
	approveRequest.submit({ request_name: requestName })
}

const handleDeny = (requestName) => {
	denyRequest.submit({ request_name: requestName })
}

const statusTheme = (status) => {
	return {
		Pending: 'orange',
		Approved: 'green',
		Denied: 'red',
	}[status] || 'gray'
}
</script>
