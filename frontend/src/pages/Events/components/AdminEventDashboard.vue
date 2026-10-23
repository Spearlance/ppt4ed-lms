<template>
	<div v-if="batch?.data" class="p-5">
		<div class="grid grid-cols-2 md:grid-cols-4 gap-5 mb-8">
			<NumberChartGraph
				:title="__('Enrolled')"
				:value="formatAmount(batch.data?.students?.length) || 0"
			/>

			<NumberChartGraph
				:title="__('Certified')"
				:value="certificationCount.data || 0"
			/>

			<NumberChartGraph
				class="border rounded-md"
				:title="__('Courses')"
				:value="batch?.data?.courses?.length || 0"
			/>

			<NumberChartGraph
				class="border rounded-md"
				:title="__('Assessments')"
				:value="batch?.data?.assessments?.length || 0"
			/>
		</div>

		<div class="grid grid-cols-1 lg:grid-cols-[3fr_2fr] gap-5 items-start">
			<div class="border rounded-lg py-3 px-4 order-2 lg:order-1">
				<div class="flex items-center justify-between space-x-2 mb-3">
					<div class="text-lg text-ink-gray-9 font-semibold">
						{{ __('Students') }}
					</div>
					<div class="flex items-center space-x-2">
						<FormControl
							v-model="searchFilter"
							:placeholder="__('Search by name')"
							type="text"
						/>
						<Button
							:loading="attendeeExport.loading"
							@click="downloadAttendees"
						>
							<template #prefix>
								<Download class="size-4 stroke-1.5" />
							</template>
							{{ __('Attendees CSV') }}
						</Button>
						<Button
							v-if="batch?.data?.survey_quiz"
							:loading="surveyExport.loading"
							@click="downloadSurveyResponses"
						>
							<template #prefix>
								<Download class="size-4 stroke-1.5" />
							</template>
							{{ __('Survey CSV') }}
						</Button>
						<Button @click="showEnrollmentModal = true">
							<template #prefix>
								<Plus class="size-4 stroke-1.5" />
							</template>
							{{ __('Enroll') }}
						</Button>
					</div>
				</div>
				<div
					v-if="students.loading || students.data?.length"
					class="max-h-[63vh] overflow-y-auto"
				>
					<ListView
						:columns="studentColumns"
						:rows="students.data"
						rowKey="name"
						:options="{
							selectable: true,
							showTooltip: false,
						}"
					>
						<ListHeader
							class="mb-2 grid items-center space-x-4 rounded bg-surface-white border-b rounded-none p-2"
						>
							<ListHeaderItem
								:item="item"
								v-for="item in studentColumns"
								:key="item.key"
							>
							</ListHeaderItem>
						</ListHeader>
						<ListRows v-for="row in students.data" class="max-h-[500px]">
							<ListRow :row="row">
								<template #default="{ column, item }">
									<ListRowItem
										:item="row[column.key]"
										:align="column.align"
										class="w-full"
									>
										<template #prefix>
											<div v-if="column.key == 'member_name'">
												<Avatar
													class="flex items-center"
													:image="row['member_image']"
													:label="item"
													size="sm"
												/>
											</div>
											<!-- <ProgressBar
												v-else-if="column.key == 'progress'"
												:progress="Math.ceil(row[column.key])"
												class="!mx-0 !mr-4"
											/> -->
										</template>
										<div v-if="column.key == 'creation'">
											{{ dayjs(row[column.key]).format('DD MMM YYYY') }}
										</div>
										<div v-else-if="column.key == 'survey'">
											<Badge
												:theme="creditFor(row.member)?.survey_submitted ? 'green' : 'gray'"
											>
												{{
													creditFor(row.member)?.survey_submitted
														? __('Submitted')
														: __('Pending')
												}}
											</Badge>
										</div>
										<div
											v-else-if="column.key == 'quiz'"
											class="flex items-center justify-end gap-2"
										>
											<Badge
												:theme="quizBadge(row.member).theme"
												:title="creditFor(row.member)?.admin_note || ''"
											>
												{{ quizBadge(row.member).label }}
											</Badge>
											<Button
												size="sm"
												variant="ghost"
												:label="
													__('Record quiz score for {0}').format(
														row.member_name || row.member
													)
												"
												@click.stop="openScoreDialog([row])"
											>
												<template #icon>
													<PencilLine class="size-4 stroke-1.5" />
												</template>
											</Button>
										</div>
										<div v-else-if="column.key == 'certificate'">
											<Badge
												:theme="creditFor(row.member)?.certificate ? 'green' : 'gray'"
											>
												{{
													creditFor(row.member)?.certificate
														? __('Issued')
														: __('Pending')
												}}
											</Badge>
										</div>
										<div
											v-else-if="column.key == 'progress'"
											class="text-xs !mx-0 w-5"
										>
											{{ Math.ceil(row[column.key]) }}%
										</div>
										<router-link
											v-else-if="
												column.key == 'member_name' && row.member_username
											"
											:to="{
												name: 'Profile',
												params: { username: row.member_username },
											}"
											class="hover:underline"
											@click.stop
										>
											{{ row[column.key].toString() }}
										</router-link>
										<div v-else>
											{{ row[column.key].toString() }}
										</div>
									</ListRowItem>
								</template>
							</ListRow>
						</ListRows>
						<ListSelectBanner class="!min-w-0 sm:!min-w-[596px]">
							<template #actions="{ unselectAll, selections }">
								<Button
									v-if="batch?.data?.certification"
									variant="ghost"
									:loading="issueCertificates.loading"
									data-testid="issue-certificate-action"
									@click="confirmIssue(selections, unselectAll)"
								>
									<template #prefix>
										<Award class="size-4 stroke-1.5" />
									</template>
									<span class="sr-only sm:not-sr-only">
										{{ __('Issue certificate') }}
									</span>
								</Button>
								<Button
									v-if="creditQuizRequired"
									variant="ghost"
									@click="openScoreDialogForSelection(selections, unselectAll)"
								>
									<template #prefix>
										<ClipboardCheck class="size-4 stroke-1.5" />
									</template>
									<span class="sr-only sm:not-sr-only">
										{{ __('Record quiz scores') }}
									</span>
								</Button>
								<Button
									variant="ghost"
									theme="red"
									:loading="removeRegistrations.loading"
									@click="confirmRemoval(selections, unselectAll)"
								>
									<template #prefix>
										<UserMinus class="size-4 stroke-1.5" />
									</template>
									<span class="sr-only sm:not-sr-only">
										{{ __('Remove from event') }}
									</span>
								</Button>
							</template>
						</ListSelectBanner>
					</ListView>
					<div
						v-if="students.data && students.hasNextPage"
						class="flex justify-center my-3"
					>
						<Button @click="students.next()">
							{{ __('Load More') }}
						</Button>
					</div>
				</div>
			</div>

			<div class="order-1 lg:order-2">
				<AxisChart
					v-if="showProgressChart"
					class="border rounded-lg p-3 min-h-[300px]"
					:config="{
						data: filteredChartData,
						title: __('Event Summary'),
						subtitle: __('Progress of students in courses and assessments'),
						xAxis: {
							key: 'task',
							title: 'Tasks',
							type: 'category',
						},
						yAxis: {
							title: __('Number of Students'),
							echartOptions: {
								minInterval: 1,
							},
						},
						series: [
							{
								name: 'value',
								type: 'bar',
							},
						],
					}"
				/>

			</div>
		</div>
	</div>
	<StudentModal
		v-if="showEnrollmentModal"
		v-model="showEnrollmentModal"
		:event="event"
		:students="students"
	/>
	<Dialog
		v-model="scoreDialog.open"
		:options="{
			title: scoreDialogTitle,
			actions: [
				{
					label: __('Save score'),
					variant: 'solid',
					loading: recordScores.loading,
					onClick: ({ close }) => saveScores(close),
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4 text-sm">
				<p class="text-ink-gray-7 leading-5">
					<template v-if="creditMode === 'In-Person Quiz'">
						{{
							__(
								'Enter the score from the in-person quiz. {0}% or higher counts as a pass and issues the certificate once the feedback survey is in.'
							).format(passingPercentage)
						}}
					</template>
					<template v-else>
						{{
							__(
								'This overrides the online quiz result. {0}% or higher counts as a pass and issues the certificate once the feedback survey is in. The override is logged on the event.'
							).format(passingPercentage)
						}}
					</template>
				</p>
				<div
					v-if="scoreDialog.rows.length > 1"
					class="rounded-md bg-surface-gray-2 px-3 py-2 text-ink-gray-7"
				>
					{{
						__('Applying the same score to {0} attendees.').format(
							scoreDialog.rows.length
						)
					}}
				</div>
				<FormControl
					v-model="scoreDialog.percentage"
					type="number"
					:label="__('Score (%)')"
					min="0"
					max="100"
					:required="true"
				/>
				<FormControl
					v-model="scoreDialog.note"
					type="textarea"
					:rows="2"
					:label="__('Note (optional)')"
					:placeholder="__('e.g. paper retake on 10/18')"
				/>
				<div
					v-if="scoreDialog.error"
					class="text-ink-red-3"
				>
					{{ scoreDialog.error }}
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import {
	AxisChart,
	createResource,
	createListResource,
	dayjs,
	FormControl,
	ListView,
	ListHeader,
	ListHeaderItem,
	ListRows,
	ListRow,
	ListRowItem,
	ListSelectBanner,
	Avatar,
	Badge,
	Button,
	Dialog,
	toast,
} from 'frappe-ui'
import { computed, getCurrentInstance, reactive, ref, watch } from 'vue'
import { formatAmount } from '@/utils'
import {
	Award,
	ClipboardCheck,
	Download,
	PencilLine,
	Plus,
	UserMinus,
} from 'lucide-vue-next'
import NumberChartGraph from '@/components/NumberChartGraph.vue'
import StudentModal from '@/components/Modals/StudentModal.vue'

const app = getCurrentInstance()
const $dialog = app?.appContext.config.globalProperties.$dialog
const searchFilter = ref<string | null>(null)
const showEnrollmentModal = ref<boolean>(false)

const props = defineProps<{
	batch: { [key: string]: any } | null
}>()

const chartData = createResource({
	url: 'lms.lms.utils.get_event_chart_data',
	cache: ['event_chart_data', props.batch?.data?.name],
	params: { batch: props.batch?.data?.name },
	auto: true,
})

const certificationCount = createResource({
	url: 'frappe.client.get_count',
	cache: ['event_certificate_count', props.batch?.data?.name],
	params: {
		doctype: 'LMS Certificate',
		filters: { event_name: props.batch?.data?.name },
	},
	auto: true,
})

const attendeeExport = createResource({
	url: 'lms.lms.api.export_event_attendees_csv',
	makeParams() {
		return { event: props.batch?.data?.name }
	},
})

const surveyExport = createResource({
	url: 'lms.lms.api.export_event_survey_responses_csv',
	makeParams() {
		return { event: props.batch?.data?.name }
	},
})

function triggerCsvDownload(res: { filename: string; csv: string }) {
	const blob = new Blob([res.csv], { type: 'text/csv;charset=utf-8;' })
	const url = URL.createObjectURL(blob)
	const a = document.createElement('a')
	a.href = url
	a.download = res.filename
	document.body.appendChild(a)
	a.click()
	document.body.removeChild(a)
	URL.revokeObjectURL(url)
}

async function downloadAttendees() {
	try {
		const res = await attendeeExport.submit()
		if (!res?.count) {
			toast.info(__('No attendees to export yet'))
			return
		}
		triggerCsvDownload(res)
	} catch (e) {
		toast.error(e.messages?.[0] || __('Could not export attendees'))
	}
}

async function downloadSurveyResponses() {
	try {
		const res = await surveyExport.submit()
		if (!res?.count) {
			toast.info(__('No survey responses yet'))
			return
		}
		triggerCsvDownload(res)
	} catch (e) {
		toast.error(e.messages?.[0] || __('Could not export survey responses'))
	}
}

const students = createListResource({
	doctype: 'LMS Event Registration',
	filters: {
		event: props.batch?.data?.name,
	},
	fields: [
		'name',
		'member',
		'member_name',
		'member_username',
		'member_image',
		'payment',
		'creation',
	],
	orderBy: 'creation desc',
	auto: true,
})

const removeRegistrations = createResource({
	url: 'lms.lms.ceu_event_admin.remove_event_registrations',
})

// --- CEU credit verification (survey / quiz / certificate per attendee) ---

const creditMode = computed<string>(
	() => props.batch?.data?.credit_verification || 'Survey Only'
)
const creditQuizRequired = computed<boolean>(
	() => Boolean(props.batch?.data?.credit_quiz_required)
)
const creditStatus = createResource({
	url: 'lms.lms.ceu_event_admin.get_event_credit_status',
	cache: ['event_credit_status', props.batch?.data?.name],
	params: { event: props.batch?.data?.name },
	auto: Boolean(props.batch?.data?.certification),
})
const passingPercentage = computed(
	() =>
		creditStatus.data?.passing_percentage ??
		props.batch?.data?.credit_passing_percentage ??
		80
)

function creditFor(member: string) {
	return creditStatus.data?.members?.[member] || null
}

function quizBadge(member: string): { theme: string; label: string } {
	const s = creditFor(member)
	if (!s) return { theme: 'gray', label: __('—') }
	const best =
		s.best_percentage !== null && s.best_percentage !== undefined
			? Math.round(s.best_percentage)
			: null
	if (s.passed) {
		const suffix = best !== null ? ` ${best}%` : ''
		return {
			theme: 'green',
			label: (s.entered_by_admin ? __('Passed (admin)') : __('Passed')) + suffix,
		}
	}
	if (best !== null) {
		return {
			theme: 'red',
			label: __('{0}% (below {1}%)').format(best, passingPercentage.value),
		}
	}
	if (creditMode.value === 'In-Person Quiz') {
		return { theme: 'gray', label: __('Not recorded') }
	}
	return { theme: 'gray', label: __('Not attempted') }
}

const scoreDialog = reactive<{
	open: boolean
	rows: Array<{ member: string; member_name?: string }>
	percentage: number | string
	note: string
	error: string
	unselectAll: null | (() => void)
}>({
	open: false,
	rows: [],
	percentage: 100,
	note: '',
	error: '',
	unselectAll: null,
})

const scoreDialogTitle = computed(() => {
	if (scoreDialog.rows.length === 1) {
		const r = scoreDialog.rows[0]
		return __('Record quiz score for {0}').format(r.member_name || r.member)
	}
	return __('Record quiz scores')
})

function openScoreDialog(
	rows: Array<{ member: string; member_name?: string }>,
	unselectAll: null | (() => void) = null
) {
	if (!creditQuizRequired.value) {
		toast.info(
			__(
				'Set Credit Verification to Online Quiz or In-Person Quiz in Settings to record scores.'
			)
		)
		return
	}
	scoreDialog.rows = rows
	scoreDialog.percentage = 100
	scoreDialog.note = ''
	scoreDialog.error = ''
	scoreDialog.unselectAll = unselectAll
	scoreDialog.open = true
}

function openScoreDialogForSelection(
	selections: Set<string>,
	unselectAll: () => void
) {
	const names = Array.from(selections || [])
	const rows = (students.data || []).filter((row: any) =>
		names.includes(row.name)
	)
	if (!rows.length) {
		toast.info(__('Select at least one attendee'))
		return
	}
	openScoreDialog(rows, unselectAll)
}

const recordScores = createResource({
	url: 'lms.lms.ceu_event_admin.record_event_quiz_results',
})

function saveScores(close: () => void) {
	const pct = Number(scoreDialog.percentage)
	if (Number.isNaN(pct) || pct < 0 || pct > 100) {
		scoreDialog.error = __('Enter a score between 0 and 100.')
		return
	}
	scoreDialog.error = ''
	recordScores
		.submit({
			event: props.batch?.data?.name,
			entries: scoreDialog.rows.map((r) => ({
				member: r.member,
				percentage: pct,
				note: scoreDialog.note,
			})),
		})
		.then((res: any) => {
			const recorded = res?.recorded || []
			const passed = recorded.filter((r: any) => r.passed)
			const minted = recorded.filter((r: any) => r.certificate)
			const awaitingSurvey = passed.filter(
				(r: any) => !r.certificate && !r.survey_submitted
			)
			if (recorded.length === 1) {
				const r = recorded[0]
				if (r.certificate) {
					toast.success(
						__('{0} passed — certificate issued').format(r.member_name)
					)
				} else if (r.passed) {
					toast.success(
						__('{0} passed — certificate will issue once their survey is in').format(
							r.member_name
						)
					)
				} else {
					toast.warning(
						__('{0} scored {1}%, below the {2}% needed').format(
							r.member_name,
							Math.round(r.percentage),
							Math.round(res.passing_percentage)
						)
					)
				}
			} else {
				toast.success(
					__('Recorded {0} scores: {1} passed, {2} certificates issued').format(
						recorded.length,
						passed.length,
						minted.length
					)
				)
				if (awaitingSurvey.length) {
					toast.info(
						__('{0} passed but still need to submit the survey').format(
							awaitingSurvey.length
						)
					)
				}
			}
			scoreDialog.unselectAll?.()
			close()
			creditStatus.reload()
			certificationCount.reload()
		})
		.catch((e: any) => {
			scoreDialog.error = e?.messages?.[0] || __('Could not record the score')
		})
}

const issueCertificates = createResource({
	url: 'lms.lms.ceu_event_admin.issue_event_certificates',
})

function confirmIssue(selections: Set<string>, unselectAll: () => void) {
	const names = Array.from(selections || [])
	const selected = (students.data || []).filter((row: any) =>
		names.includes(row.name)
	)
	if (!selected.length) {
		toast.info(__('Select at least one attendee to certify'))
		return
	}
	const who =
		selected.length === 1
			? selected[0].member_name || selected[0].member
			: __('{0} attendees').format(selected.length)
	const alreadyIssued = selected.filter(
		(row: any) => creditFor(row.member)?.certificate
	).length
	let message = __(
		'Each attendee gets the event certificate right away and is emailed a copy. No survey or quiz result is checked.'
	)
	if (alreadyIssued) {
		message +=
			' ' +
			__('{0} of them already have one and will be skipped.').format(alreadyIssued)
	}

	$dialog({
		title: __('Issue certificate to {0}?').format(who),
		message,
		actions: [
			{
				label: __('Issue certificate'),
				variant: 'solid',
				onClick({ close }: { close: () => void }) {
					issueCertificates
						.submit({
							event: props.batch?.data?.name,
							members: selected.map((row: any) => row.member),
						})
						.then((res: any) => {
							const issued = res?.issued || []
							const skipped = res?.skipped || []
							if (issued.length === 1) {
								toast.success(
									__('Certificate issued to {0}').format(issued[0].member_name)
								)
							} else if (issued.length) {
								toast.success(__('Issued {0} certificates').format(issued.length))
							}
							if (skipped.length) {
								toast.info(
									__('{0} already certified, skipped').format(skipped.length)
								)
							}
							unselectAll()
							close()
							creditStatus.reload()
							certificationCount.reload()
						})
						.catch((e: any) => {
							toast.error(e?.messages?.[0] || __('Could not issue certificates'))
						})
				},
			},
		],
	})
}

function confirmRemoval(selections: Set<string>, unselectAll: () => void) {
	const names = Array.from(selections || [])
	if (!names.length) {
		toast.info(__('Select at least one person to remove'))
		return
	}
	const selected = (students.data || []).filter((row: any) =>
		names.includes(row.name)
	)
	const who =
		selected.length === 1
			? selected[0].member_name || selected[0].member
			: __('{0} people').format(names.length)
	const paidCount = selected.filter((row: any) => row.payment).length
	let message = __(
		'Their seat opens up right away and they stop getting reminders for this event. Nobody is emailed about the removal.'
	)
	if (paidCount) {
		message +=
			' ' +
			__(
				'{0} of them paid for this event. Removing them does not issue a refund, so handle that in Stripe.'
			).format(paidCount)
	}

	$dialog({
		title: __('Remove {0} from this event?').format(who),
		message,
		actions: [
			{
				label: __('Remove'),
				theme: 'red',
				variant: 'solid',
				onClick({ close }: { close: () => void }) {
					removeRegistrations
						.submit({
							event: props.batch?.data?.name,
							registrations: names,
						})
						.then((res: any) => {
							const count = res?.removed?.length || 0
							toast.success(
								count === 1
									? __('Removed {0} from the event').format(
											res.removed[0].member_name
									  )
									: __('Removed {0} people from the event').format(count)
							)
							if (res?.paid?.length) {
								toast.warning(
									__('Refund still needed in Stripe for: {0}').format(
										res.paid.map((p: any) => p.member_name).join(', ')
									)
								)
							}
							unselectAll()
							close()
							students.reload()
							chartData.reload()
							props.batch?.reload?.()
						})
						.catch((e: any) => {
							toast.error(
								e?.messages?.[0] || __('Could not remove registration')
							)
						})
				},
			},
		],
	})
}

const filteredChartData = computed(() =>
	(chartData.data || []).filter((item: { value: number }) => item.value > 0)
)

watch(searchFilter, () => {
	let filters: Record<string, any> = {
		event: props.batch?.data?.name,
	}

	if (searchFilter.value) {
		filters.member_name = ['like', `%${searchFilter.value}%`]
	}

	students.update({ filters })
	students.reload()
})

const studentColumns = computed(() => {
	const columns: Array<Record<string, any>> = [
		{
			label: __('Name'),
			key: 'member_name',
			width: '40%',
		},
	]
	if (props.batch?.data?.certification) {
		if (props.batch?.data?.survey_quiz) {
			columns.push({ label: __('Survey'), key: 'survey', align: 'right' })
		}
		if (creditQuizRequired.value) {
			columns.push({ label: __('Quiz'), key: 'quiz', align: 'right' })
		}
		columns.push({ label: __('Certificate'), key: 'certificate', align: 'right' })
	}
	columns.push({
		label: __('Enrolled On'),
		key: 'creation',
		align: 'right',
	})
	return columns
})

const showProgressChart = computed(
	() =>
		students.data?.length &&
		(props.batch?.data?.courses?.length ||
			props.batch?.data?.assessments?.length)
)
</script>
