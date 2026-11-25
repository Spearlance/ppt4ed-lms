<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Enroll a Student'),
			size: 'lg',
			actions: [
				{
					label: 'Submit',
					variant: 'solid',
					onClick: (close) => addStudent(close),
				},
			],
		}"
	>
		<template #body-content>
			<div class="flex flex-col gap-4">
				<Link
					doctype="User"
					v-model="student"
					placeholder=" "
					:label="__('Student')"
					:onCreate="
						() => {
							openSettings('Members')
							show = false
						}
					"
					:required="true"
				/>
				<Link
					doctype="LMS Payment"
					v-model="payment"
					placeholder=" "
					:label="__('Payment')"
					:onCreate="
						() => {
							openSettings('Transactions')
							show = false
						}
					"
				/>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { call, Dialog, toast } from 'frappe-ui'
import { ref, inject } from 'vue'
import { useOnboarding } from 'frappe-ui/frappe'
import { openSettings } from '@/utils'
import Link from '@/components/Controls/Link.vue'

const student = ref(null)
const payment = ref(null)
const user = inject('$user')
const { updateOnboardingStep } = useOnboarding('learning')
const show = defineModel()

const props = defineProps({
	batch: {
		type: Object,
		default: null,
	},
	students: {
		type: Object,
		default: null,
	},
})

// Goes through a server method rather than a client-side insert: the old
// insert sent the event under its pre-rename field name (`batch`), so the
// registration was rejected, and Global Admins are not covered by the
// doctype's permission rows.
const addStudent = async (close) => {
	if (!student.value) {
		toast.error(__('Please choose a student.'))
		return
	}
	try {
		await call('lms.lms.event_private_link.register_member', {
			event: props.batch.data?.name,
			member: student.value,
			payment: payment.value,
		})
		if (user.data?.is_system_manager) updateOnboardingStep('add_batch_student')
		student.value = null
		payment.value = null
		props.students?.reload()
		props.batch.reload()
		close()
	} catch (err) {
		toast.error(String(err.messages?.[0] || err.message || err).replace(/<[^>]+>/g, ''))
		console.error(err)
	}
}
</script>
