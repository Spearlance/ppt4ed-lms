<template>
	<div class="w-[90%] lg:w-[75%] mx-auto mt-5">
		<div class="text-ink-gray-9 font-semibold text-lg mb-4">
			{{ __('Feedback Survey') }}
		</div>

		<div
			v-if="!batch.data?.survey_quiz"
			class="border border-dashed border-outline-gray-2 rounded-md py-12 px-6 text-center"
		>
			<ClipboardList
				class="w-8 h-8 stroke-1.5 mx-auto text-ink-gray-5 mb-2"
			/>
			<div class="text-ink-gray-7 leading-5">
				{{ __('No feedback survey is configured for this event.') }}
			</div>
		</div>

		<div
			v-else-if="!batch.data?.survey_open"
			class="bg-surface-blue-2 text-ink-blue-3 rounded-md p-4 leading-5"
		>
			{{
				__(
					'The feedback survey opens 30 minutes before the end of the final session.'
				)
			}}
		</div>

		<div
			v-else-if="batch.data?.survey_submitted && !justSubmitted"
			class="bg-surface-green-1 text-ink-green-3 rounded-md p-4 leading-5"
		>
			{{ submittedMessage }}
			<router-link
				v-if="quizStillNeeded && batch.data?.credit_verification === 'Online Quiz'"
				:to="{ hash: '#quiz' }"
				replace
				class="underline ml-1"
			>
				{{ __('Take Quiz') }}
			</router-link>
		</div>

		<Quiz
			v-else
			:quizName="batch.data.survey_quiz"
			submitUrl="lms.lms.api.submit_event_survey"
			:submitExtraParams="{ event: batch.data.name }"
			@submitted="onSubmitted"
		/>
	</div>
</template>
<script setup>
import { computed, ref } from 'vue'
import { ClipboardList } from 'lucide-vue-next'
import Quiz from '@/components/Quiz.vue'

const props = defineProps({
	batch: {
		type: Object,
		required: true,
	},
})

const justSubmitted = ref(false)

const quizStillNeeded = computed(() => {
	const data = props.batch.data
	return Boolean(data?.credit_quiz_required && !data?.credit_status?.passed)
})

const submittedMessage = computed(() => {
	const data = props.batch.data
	if (data?.credit_verification === 'Manual' && !data?.certificate) {
		return __(
			'Thanks for your feedback! Your certificate will be issued by the event organizer after the event.'
		)
	}
	if (!quizStillNeeded.value || data?.certificate) {
		return __(
			"Thanks for your feedback! Your certificate has been issued — you'll find it in your account."
		)
	}
	if (data?.credit_verification === 'In-Person Quiz') {
		return __(
			'Thanks for your feedback! Your certificate will be issued once your instructor records your quiz score.'
		)
	}
	return __(
		'Thanks for your feedback! Pass the credit quiz to receive your certificate.'
	)
})

const onSubmitted = () => {
	justSubmitted.value = true
	props.batch.reload?.()
}
</script>
