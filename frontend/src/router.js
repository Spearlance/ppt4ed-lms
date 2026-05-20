import { createRouter, createWebHistory } from 'vue-router'
import { usersStore } from './stores/user'
import { sessionStore } from './stores/session'
import { useSettings } from './stores/settings'
import { getLmsBasePath } from './utils/basePath'

const routes = [
	{
		path: '/',
		name: 'Home',
		component: () => import('@/pages/Home/Home.vue'),
	},
	{
		path: '/courses',
		name: 'Courses',
		component: () => import('@/pages/Courses/Courses.vue'),
	},
	{
		path: '/courses/:courseName',
		name: 'CourseDetail',
		component: () => import('@/pages/Courses/CourseDetail.vue'),
		props: true,
	},
	{
		path: '/courses/:courseName/learn/:chapterNumber-:lessonNumber',
		name: 'Lesson',
		component: () => import('@/pages/Lesson.vue'),
		props: true,
	},
	{
		path: '/courses/:courseName/learn/:chapterName',
		name: 'SCORMChapter',
		component: () => import('@/pages/SCORMChapter.vue'),
		props: true,
	},
	{
		path: '/resources',
		name: 'Resources',
		component: () => import('@/pages/Resources/Resources.vue'),
	},
	{
		path: '/resources/:resourceName',
		name: 'ResourceDetail',
		component: () => import('@/pages/Resources/ResourceDetail.vue'),
		props: true,
	},
	{
		path: '/events',
		name: 'Events',
		component: () => import('@/pages/Events/Events.vue'),
	},
	{
		path: '/batches',
		redirect: '/events',
	},
	{
		path: '/batches/details/:eventName',
		redirect: (to) => `/events/${to.params.eventName}`,
	},
	{
		path: '/batches/:eventName',
		redirect: (to) => `/events/${to.params.eventName}`,
	},
	{
		path: '/events/details/:eventName',
		redirect: (to) => `/events/${to.params.eventName}`,
	},
	{
		path: '/events/:eventName',
		name: 'EventDetail',
		component: () => import('@/pages/Events/EventDetail.vue'),
		props: true,
	},
	{
		path: '/community-events',
		name: 'CommunityEvents',
		component: () => import('@/pages/CommunityEvents/CommunityEvents.vue'),
	},
	{
		path: '/community-events/:slug',
		name: 'CommunityEventForm',
		component: () => import('@/pages/CommunityEvents/CommunityEventForm.vue'),
		props: true,
	},
	{
		path: '/statistics',
		name: 'Statistics',
		component: () => import('@/pages/Statistics.vue'),
	},
	{
		path: '/user/:username',
		name: 'Profile',
		component: () => import('@/pages/Profile.vue'),
		props: true,
		redirect: { name: 'ProfileAbout' },
		children: [
			{
				name: 'ProfileAbout',
				path: '',
				component: () => import('@/pages/ProfileAbout.vue'),
			},
			{
				name: 'ProfileCertificates',
				path: 'certificates',
				component: () => import('@/pages/ProfileCertificates.vue'),
			},
			{
				name: 'ProfileRoles',
				path: 'roles',
				component: () => import('@/pages/ProfileRoles.vue'),
			},
			{
				name: 'ProfileMembership',
				path: 'membership',
				component: () => import('@/pages/ProfileMembership.vue'),
			},
		],
	},
	{
		path: '/courses/:courseName/learn/:chapterNumber-:lessonNumber/edit',
		name: 'LessonForm',
		component: () => import('@/pages/LessonForm.vue'),
		props: true,
	},
	{
		path: '/certified-participants',
		name: 'CertifiedParticipants',
		component: () => import('@/pages/CertifiedParticipants.vue'),
	},
	{
		path: '/notifications',
		name: 'Notifications',
		component: () => import('@/pages/Notifications.vue'),
	},
	{
		path: '/quizzes',
		name: 'Quizzes',
		component: () => import('@/pages/Quizzes.vue'),
	},
	{
		path: '/quizzes/:quizID',
		name: 'QuizForm',
		component: () => import('@/pages/QuizForm.vue'),
		props: true,
	},
	{
		path: '/quiz/:quizID',
		name: 'QuizPage',
		component: () => import('@/pages/QuizPage.vue'),
		props: true,
	},
	{
		path: '/quiz-submissions/:quizID',
		name: 'QuizSubmissionList',
		component: () => import('@/pages/QuizSubmissionList.vue'),
		props: true,
	},
	{
		path: '/quiz-submission/:submission',
		name: 'QuizSubmission',
		component: () => import('@/pages/QuizSubmission.vue'),
		props: true,
	},
	{
		path: '/programs',
		name: 'Programs',
		component: () => import('@/pages/Programs/Programs.vue'),
	},
	{
		path: '/programs/:programName',
		name: 'ProgramDetail',
		component: () => import('@/pages/Programs/ProgramDetail.vue'),
		props: true,
	},
	{
		path: '/assignments',
		name: 'Assignments',
		component: () => import('@/pages/Assignments.vue'),
	},
	{
		path: '/assignment-submission/:assignmentID/:submissionName',
		name: 'AssignmentSubmission',
		component: () => import('@/pages/AssignmentSubmission.vue'),
		props: true,
	},
	{
		path: '/assignment-submissions',
		name: 'AssignmentSubmissionList',
		component: () => import('@/pages/AssignmentSubmissionList.vue'),
	},
	{
		path: '/search',
		name: 'Search',
		component: () => import('@/pages/Search/Search.vue'),
	},
	{
		path: '/my-credits',
		name: 'MyCredits',
		component: () => import('@/pages/MyCredits.vue'),
	},
	{
		path: '/company-dashboard',
		name: 'CompanyDashboard',
		component: () => import('@/pages/CompanyDashboard.vue'),
	},
	{
		path: '/admin-reports',
		name: 'AdminReports',
		component: () => import('@/pages/AdminReports.vue'),
	},
	{
		path: '/admin-categories',
		name: 'AdminCategories',
		component: () => import('@/pages/AdminCategories.vue'),
	},
	{
		path: '/data-import',
		name: 'DataImportList',
		component: () => import('@/pages/DataImport.vue'),
	},
	{
		path: '/data-import/doctype/:doctype',
		name: 'NewDataImport',
		component: () => import('@/pages/DataImport.vue'),
		props: true,
	},
	{
		path: '/data-import/:importName',
		name: 'DataImport',
		component: () => import('@/pages/DataImport.vue'),
		props: true,
	},
	{
		path: '/membership-plans',
		name: 'MembershipPlans',
		component: () => import('@/pages/MembershipPlans.vue'),
	},
	{
		path: '/admin/company/:companyName',
		name: 'CompanyAdmin',
		component: () => import('@/pages/CompanyAdmin.vue'),
		props: true,
	},
	{
		path: '/admin/certificate-preview/:certName',
		name: 'CertificatePreview',
		component: () => import('@/pages/AdminCertificatePreview.vue'),
		props: true,
	},
	{
		path: '/privacy',
		name: 'PrivacyPolicy',
		component: () => import('@/pages/Legal/PrivacyPolicy.vue'),
	},
	{
		path: '/terms',
		name: 'TermsOfService',
		component: () => import('@/pages/Legal/TermsOfService.vue'),
	},
	{
		path: '/cookies',
		name: 'CookiePolicy',
		component: () => import('@/pages/Legal/CookiePolicy.vue'),
	},
	{
		path: '/signup',
		name: 'Signup',
		component: () => import('@/pages/Signup.vue'),
	},
	{
		path: '/invite/:token',
		name: 'AcceptInvite',
		component: () => import('@/pages/AcceptInvite.vue'),
		props: true,
	},
]

let router = createRouter({
	history: createWebHistory(`/${getLmsBasePath()}`),
	routes,
})

const lmsAdminOnlyRoutes = ['Statistics', 'AdminReports', 'CertificatePreview']
const moderatorOnlyRoutes = ['CommunityEvents', 'CommunityEventForm', 'AdminCategories']

router.beforeEach(async (to, from, next) => {
	const { userResource } = usersStore()
	let { isLoggedIn } = sessionStore()
	const { settings } = useSettings()

	try {
		if (isLoggedIn) {
			await userResource.promise
		}
	} catch (error) {
		isLoggedIn = false
	}

	if (!isLoggedIn) {
		if (to.name == 'Home') router.push({ name: 'Courses' })

		// Guests on a Resource detail page get the public Jinja landing at
		// /r/<slug>, which carries the same hero + the standard register
		// modal flow (target_type='resource' → signup_and_enroll auto-claims
		// the resource on success). The in-app /lms/resources/<slug> view is
		// authenticated-only.
		if (to.name === 'ResourceDetail' && to.params.resourceName) {
			window.location.href = `/r/${to.params.resourceName}`
			return
		}

		await settings.promise
		const guestAllowedRoutes = [
			'Resources',
			'PrivacyPolicy',
			'TermsOfService',
			'CookiePolicy',
			'Signup',
			'AcceptInvite',
			'MembershipPlans',
		]
		if (!settings.data.allow_guest_access && !guestAllowedRoutes.includes(to.name)) {
			window.location.href = '/login'
			return
		}
	}

	if (
		lmsAdminOnlyRoutes.includes(to.name) &&
		!userResource?.data?.is_lms_admin
	) {
		return next({ name: 'Courses' })
	}

	if (
		moderatorOnlyRoutes.includes(to.name) &&
		!userResource?.data?.is_moderator
	) {
		return next({ name: 'Courses' })
	}

	return next()
})

export default router
