<template>
	<div class="p-5">
		<!-- Add Member -->
		<div class="flex items-end gap-3 mb-6 pb-6 border-b">
			<div class="flex-1 max-w-xs">
				<label class="block text-sm font-medium text-ink-gray-7 mb-1">
					{{ __('Add Member') }}
				</label>
				<FormControl
					v-model="newMemberUser"
					type="text"
					:placeholder="__('user@example.com')"
				/>
			</div>
			<Button
				variant="solid"
				:loading="addMemberResource.loading"
				@click="addMember"
			>
				{{ __('Add') }}
			</Button>
		</div>

		<!-- Members Table -->
		<div v-if="company.data?.members?.length" class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b text-left text-ink-gray-5">
						<th class="pb-2 pr-4 font-medium">{{ __('Name') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Email') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Status') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Enrollments') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Last Active') }}</th>
						<th class="pb-2 font-medium">{{ __('Actions') }}</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="member in company.data.members"
						:key="member.user"
						class="border-b last:border-0"
					>
						<td class="py-3 pr-4 font-medium text-ink-gray-9">
							{{ member.full_name }}
						</td>
						<td class="py-3 pr-4 text-ink-gray-7">
							{{ member.email }}
						</td>
						<td class="py-3 pr-4">
							<Badge :theme="member.status === 'Active' ? 'green' : 'orange'">
								{{ member.status }}
							</Badge>
						</td>
						<td class="py-3 pr-4 text-ink-gray-7">
							{{ member.enrollment_count }}
						</td>
						<td class="py-3 pr-4 text-ink-gray-5">
							{{ member.last_active ? dayjs(member.last_active).fromNow() : __('Never') }}
						</td>
						<td class="py-3">
							<div class="flex items-center gap-2">
								<Button
									size="sm"
									variant="outline"
									:loading="promoteResource.loading && actionTarget === member.user"
									@click="promoteToAdmin(member.user)"
								>
									{{ __('Promote') }}
								</Button>
								<Button
									size="sm"
									theme="red"
									variant="subtle"
									:loading="removeResource.loading && actionTarget === member.user"
									@click="removeMember(member.user)"
								>
									{{ __('Remove') }}
								</Button>
							</div>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div v-else-if="company.loading" class="text-center py-10 text-ink-gray-5">
			{{ __('Loading...') }}
		</div>
		<div v-else class="text-center py-10 text-ink-gray-5">
			{{ __('No members yet.') }}
		</div>
	</div>
</template>

<script setup>
import { ref } from 'vue'
import { Badge, Button, FormControl, createResource, toast } from 'frappe-ui'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'

dayjs.extend(relativeTime)

const props = defineProps({
	company: {
		type: Object,
		required: true,
	},
})

const newMemberUser = ref('')
const actionTarget = ref(null)

const addMemberResource = createResource({
	url: 'lms.lms.api.add_member_to_company',
	onSuccess() {
		toast({ title: __('Member added'), icon: 'check', iconClasses: 'text-green-500' })
		newMemberUser.value = ''
		props.company.reload()
	},
	onError(err) {
		toast({ title: __('Error'), text: err.message, icon: 'x', iconClasses: 'text-red-500' })
	},
})

const removeResource = createResource({
	url: 'lms.lms.ceu_admin.admin_remove_member_from_company',
	onSuccess() {
		toast({ title: __('Member removed'), icon: 'check', iconClasses: 'text-green-500' })
		actionTarget.value = null
		props.company.reload()
	},
	onError(err) {
		toast({ title: __('Error'), text: err.message, icon: 'x', iconClasses: 'text-red-500' })
		actionTarget.value = null
	},
})

const promoteResource = createResource({
	url: 'lms.lms.ceu_admin.admin_promote_to_company_admin',
	onSuccess() {
		toast({ title: __('Promoted to admin'), icon: 'check', iconClasses: 'text-green-500' })
		actionTarget.value = null
		props.company.reload()
	},
	onError(err) {
		toast({ title: __('Error'), text: err.message, icon: 'x', iconClasses: 'text-red-500' })
		actionTarget.value = null
	},
})

const addMember = () => {
	if (!newMemberUser.value.trim()) return
	addMemberResource.submit({
		company: props.company.data.name,
		user: newMemberUser.value.trim(),
	})
}

const removeMember = (user) => {
	actionTarget.value = user
	removeResource.submit({
		company: props.company.data.name,
		user,
	})
}

const promoteToAdmin = (user) => {
	actionTarget.value = user
	promoteResource.submit({
		company: props.company.data.name,
		user,
	})
}
</script>
