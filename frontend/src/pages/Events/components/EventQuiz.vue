<template>
	<div class="w-[90%] lg:w-[75%] mx-auto mt-5">
		<div class="text-ink-gray-9 font-semibold text-lg mb-4">
			{{ __('Credit Quiz') }}
		</div>

		<div
			v-if="!batch.data?.credit_quiz"
			class="border border-dashed border-outline-gray-2 rounded-md py-12 px-6 text-center"
		>
			<ClipboardCheck
				class="w-8 h-8 stroke-1.5 mx-auto text-ink-gray-5 mb-2"
			/>
			<div class="text-ink-gray-7 leading-5">
				{{ __('No credit quiz is configured for this event.') }}
			</div>
		</div>

		<div
			v-else-if="!batch.data?.credit_quiz_open"
			class="bg-surface-blue-2 text-ink-blue-3 rounded-md p-4 leading-5"
		>
			{{
				__(
					'The quiz opens 30 minutes before the end of the final session.'
				)
			}}
		</div>

		<div
			v-else-if="status?.passed && !justSubmitted"
			class="bg-surface-green-1 text-ink-green-3 rounded-md p-4 leading-5"
		>
			<template v-if="batch.data?.certificate">
				{{
					__(
						"You passed the quiz and your certificate has been issued — you'll find it in your account."
					)
				}}
			</template>
			<template v-else-if="batch.data?.survey_quiz && !batch.data?.survey_submitted">
				{{
					__(
						'You passed the quiz. Submit the feedback survey to receive your certificate.'
					)
				}}
				<router-link :to="{ hash: '#survey' }" replace class="underline ml-1">
					{{ __('Take Survey') }}
				</router-link>
			</template>
			<template v-else>
				{{ __('You passed the quiz.') }}
			</template>
		</div>

		<div
			v-else-if="status?.attempts_exhausted && !justSubmitted"
			class="bg-surface-red-1 text-ink-red-3 rounded-md p-4 leading-5"
		>
			{{
				__(
					'You have used all {0} attempts for this quiz without reaching {1}%. Contact your instructor about a retake.'
				).format(status.max_attempts, status.passing_percentage)
			}}
		</div>

		<Quiz
			v-else
			:quizName="batch.data.credit_quiz"
			submitUrl="lms.lms.api.submit_event_quiz"
			:submitExtraParams="{ event: batch.data.name }"
			:attemptFilters="{ event_name: batch.data.name }"
			@submitted="onSubmitted"
		/>

		<div
			v-if="justSubmitted && lastResult"
			class="mt-4 rounded-md p-4 leading-5"
			:class="
				lastResult.pass
					? 'bg-surface-green-1 text-ink-green-3'
					: 'bg-surface-amber-1 text-ink-amber-3'
			"
		>
			<template v-if="lastResult.pass && lastResult.certificate">
				{{
					__(
						"You passed! Your certificate has been issued — you'll find it in your account."
					)
				}}
			</template>
			<template v-else-if="lastResult.pass">
				{{
					__(
						'You passed! Submit the feedback survey to receive your certificate.'
					)
				}}
				<router-link :to="{ hash: '#survey' }" replace class="underline ml-1">
					{{ __('Take Survey') }}
				</router-link>
			</template>
			<template v-else>
				{{
					__(
						'You scored {0}%, below the {1}% needed. You can try again if attempts remain.'
					).format(Math.round(lastResult.percentage || 0), status?.passing_percentage || '')
				}}
			</template>
		</div>
	</div>
</template>
<script setup>
import { computed, ref } from 'vue'
import { ClipboardCheck } from 'lucide-vue-next'
import Quiz from '@/components/Quiz.vue'

const props = defineProps({
	batch: {
		type: Object,
		required: true,
	},
})

const justSubmitted = ref(false)
const lastResult = ref(null)

const status = computed(() => props.batch.data?.credit_status || null)

const onSubmitted = (data) => {
	justSubmitted.value = true
	lastResult.value = data || null
	props.batch.reload?.()
}
</script>
