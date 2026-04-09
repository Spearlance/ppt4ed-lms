<template>
	<div class="p-5">
		<div class="flex items-center gap-3 mb-5">
			<FormControl
				v-model="newEmail"
				type="email"
				:placeholder="__('Email address')"
				class="flex-1"
			/>
			<Button
				variant="solid"
				:loading="sendInvite.loading"
				@click="handleSendInvite"
			>
				{{ __('Send Invite') }}
			</Button>
		</div>

		<div v-if="invites.data?.length" class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b text-left text-ink-gray-5">
						<th class="pb-2 pr-4 font-medium">{{ __('Email') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Status') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Sent') }}</th>
						<th class="pb-2 font-medium">{{ __('Actions') }}</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="invite in invites.data"
						:key="invite.name"
						class="border-b last:border-0"
					>
						<td class="py-3 pr-4 text-ink-gray-9">
							{{ invite.email }}
						</td>
						<td class="py-3 pr-4">
							<Badge
								:theme="statusTheme(invite.status)"
							>
								{{ invite.status }}
							</Badge>
						</td>
						<td class="py-3 pr-4 text-ink-gray-5">
							{{ dayjs(invite.creation).fromNow() }}
						</td>
						<td class="py-3">
							<Button
								v-if="invite.status === 'Pending'"
								variant="subtle"
								theme="red"
								size="sm"
								:loading="revokeInvite.loading"
								@click="handleRevoke(invite.name)"
							>
								{{ __('Revoke') }}
							</Button>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div v-else-if="invites.loading" class="text-center py-10 text-ink-gray-5">
			{{ __('Loading...') }}
		</div>
		<div v-else class="text-center py-10 text-ink-gray-5">
			{{ __('No invites sent yet.') }}
		</div>
	</div>
</template>

<script setup>
import { ref } from 'vue'
import { Badge, Button, FormControl, createResource } from 'frappe-ui'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'

dayjs.extend(relativeTime)

const newEmail = ref('')

const invites = createResource({
	url: 'lms.lms.ceu_company_dashboard.get_company_invites',
	cache: ['company-invites'],
	auto: true,
})

const sendInvite = createResource({
	url: 'lms.lms.ceu_company_dashboard.send_company_invite',
	onSuccess() {
		newEmail.value = ''
		invites.reload()
	},
})

const revokeInvite = createResource({
	url: 'lms.lms.ceu_company_dashboard.revoke_company_invite',
	onSuccess() {
		invites.reload()
	},
})

const handleSendInvite = () => {
	if (!newEmail.value) return
	sendInvite.submit({ email: newEmail.value })
}

const handleRevoke = (inviteName) => {
	revokeInvite.submit({ invite_name: inviteName })
}

const statusTheme = (status) => {
	return {
		Pending: 'orange',
		Accepted: 'green',
		Revoked: 'red',
		Expired: 'gray',
	}[status] || 'gray'
}
</script>
