<template>
    <div>
        <header
            class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
        >
            <Breadcrumbs
                class="h-7"
                :items="[{ label: __('Membership Plans'), route: { name: 'MembershipPlans' } }]"
            />
        </header>
        <div class="p-5 pb-10 max-w-6xl mx-auto">
            <div class="text-center mb-8">
                <h1 class="text-2xl font-bold text-ink-gray-9">
                    {{ __('Choose Your Plan') }}
                </h1>
                <p class="text-ink-gray-5 mt-2">
                    {{ __('Get access to CEU courses with a membership plan') }}
                </p>
            </div>

            <div v-if="plans.data" class="flex flex-col items-center">
                <!-- Tab toggle -->
                <div class="flex bg-surface-gray-2 rounded-lg p-1 mb-8">
                    <button
                        v-for="tab in tabs"
                        :key="tab.value"
                        class="px-6 py-2 rounded-md text-sm font-medium transition-all"
                        :class="activeTab === tab.value
                            ? 'bg-surface-white text-ink-gray-9 shadow-sm'
                            : 'text-ink-gray-5 hover:text-ink-gray-7'"
                        @click="activeTab = tab.value"
                    >
                        {{ tab.label }}
                    </button>
                </div>

                <!-- Company plans: horizontal comparison -->
                <div v-if="activeTab === 'Company'" class="w-full">
                    <div
                        class="grid gap-4"
                        :style="{ gridTemplateColumns: `repeat(${companyPlans.length}, minmax(0, 1fr))` }"
                    >
                        <div
                            v-for="plan in companyPlans"
                            :key="plan.name"
                            class="border rounded-xl p-6 flex flex-col relative"
                            :class="plan.is_recommended
                                ? 'border-blue-400 bg-surface-blue-2 ring-2 ring-blue-100'
                                : 'border-outline-gray-3'"
                        >
                            <div
                                v-if="plan.is_recommended"
                                class="absolute -top-3 left-1/2 -translate-x-1/2"
                            >
                                <Badge theme="blue" size="lg">
                                    {{ __('Most Popular') }}
                                </Badge>
                            </div>
                            <h3 class="text-lg font-semibold text-ink-gray-9 mt-1">
                                {{ plan.title }}
                            </h3>
                            <div class="mt-4">
                                <span class="text-3xl font-bold text-ink-gray-9">
                                    ${{ formatPrice(plan.price) }}
                                </span>
                                <span class="text-sm text-ink-gray-5">/year</span>
                            </div>
                            <div class="text-sm text-ink-gray-5 mt-2 mb-6">
                                {{ plan.ceu_hours }} CEU hours included
                            </div>
                            <div class="mt-auto space-y-3">
                                <FormControl
                                    v-model="companyNames[plan.name]"
                                    :label="__('Company Name')"
                                    placeholder="Your Company Name"
                                    type="text"
                                />
                                <Button
                                    class="w-full"
                                    :variant="plan.is_recommended ? 'solid' : 'outline'"
                                    :theme="plan.is_recommended ? 'blue' : 'gray'"
                                    :loading="checkingOut === plan.name"
                                    @click="startCheckout(plan)"
                                >
                                    {{ __('Get Started') }}
                                </Button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Individual plans: centered two-card layout -->
                <div v-else class="w-full max-w-2xl">
                    <div class="grid md:grid-cols-2 gap-6">
                        <div
                            v-for="plan in individualPlans"
                            :key="plan.name"
                            class="border rounded-xl p-6 flex flex-col"
                            :class="plan.is_recommended
                                ? 'border-blue-400 bg-surface-blue-2 ring-2 ring-blue-100'
                                : 'border-outline-gray-3'"
                        >
                            <div class="flex items-center justify-between mb-2">
                                <h3 class="text-lg font-semibold text-ink-gray-9">
                                    {{ plan.title }}
                                </h3>
                                <Badge :theme="plan.plan_type === 'Individual-Business' ? 'orange' : 'green'">
                                    {{ plan.plan_type === 'Individual-Business' ? __('Business') : __('Professional') }}
                                </Badge>
                            </div>
                            <div class="mt-2">
                                <span class="text-3xl font-bold text-ink-gray-9">
                                    ${{ formatPrice(plan.price) }}
                                </span>
                                <span class="text-sm text-ink-gray-5">/year</span>
                            </div>
                            <div class="text-sm text-ink-gray-5 mt-2 mb-6">
                                {{ plan.ceu_hours }} CEU hours included
                            </div>
                            <Button
                                class="mt-auto w-full"
                                variant="solid"
                                :loading="checkingOut === plan.name"
                                @click="startCheckout(plan)"
                            >
                                {{ __('Get Started') }}
                            </Button>
                        </div>
                    </div>
                </div>
            </div>

            <div v-else-if="plans.loading" class="text-center py-20 text-ink-gray-5">
                {{ __('Loading plans...') }}
            </div>
        </div>

        <!-- Company name dialog for when they click without entering a name -->
        <Dialog
            v-model="showCompanyDialog"
            :options="{
                title: __('Enter Company Name'),
                actions: [
                    {
                        label: __('Continue to Checkout'),
                        variant: 'solid',
                        onClick: ({ close }) => confirmCompanyCheckout(close),
                    },
                ],
            }"
        >
            <template #body-content>
                <FormControl
                    v-model="pendingCompanyName"
                    :label="__('Company Name')"
                    placeholder="Acme Corp"
                    type="text"
                    :required="true"
                />
            </template>
        </Dialog>

        <RegisterModal
            v-model:open="showRegister"
            :intent="registerIntent"
            :context-label="registerContextLabel"
            redirect-url="/lms/membership-plans"
        />
    </div>
</template>

<script setup>
import { Badge, Breadcrumbs, Button, createResource, Dialog, FormControl, toast, usePageMeta, call } from 'frappe-ui'
import { computed, inject, reactive, ref } from 'vue'
import { sessionStore } from '@/stores/session'
import RegisterModal from '@/components/Modals/RegisterModal.vue'

const user = inject('$user')
const { brand } = sessionStore()
const activeTab = ref('Company')
const checkingOut = ref(null)
const companyNames = reactive({})
const showCompanyDialog = ref(false)
const pendingCompanyName = ref('')
const pendingPlan = ref(null)
const showRegister = ref(false)
const registerIntent = ref('free')
const registerContextLabel = ref('')

const tabs = [
    { label: __('Company'), value: 'Company' },
    { label: __('Individual'), value: 'Individual' },
]

const plans = createResource({
    url: 'lms.lms.api.get_membership_plans',
    auto: true,
})

const companyPlans = computed(() =>
    (plans.data || []).filter(p => p.plan_type === 'Company')
)

const individualPlans = computed(() =>
    (plans.data || []).filter(p => p.plan_type !== 'Company')
)

const formatPrice = (price) => {
    return Number(price).toLocaleString('en-US', { maximumFractionDigits: 0 })
}

const startCheckout = async (plan) => {
    if (!user?.data?.name) {
        // Guest path: open the unified register modal. signup_and_enroll
        // will create the user, log them in, and bounce to Stripe Checkout
        // for the chosen plan. Company-name capture for guests on Company
        // plans is a v2 follow-up — for now they sign up first then attach
        // their company on the dashboard.
        registerIntent.value = `membership:${plan.name}`
        registerContextLabel.value = plan.title
        showRegister.value = true
        return
    }

    if (plan.plan_type === 'Company' && !companyNames[plan.name]?.trim()) {
        pendingPlan.value = plan
        pendingCompanyName.value = ''
        showCompanyDialog.value = true
        return
    }

    await doCheckout(plan, companyNames[plan.name] || null)
}

const confirmCompanyCheckout = async (close) => {
    if (!pendingCompanyName.value?.trim()) {
        toast.error(__('Company name is required'))
        return
    }
    companyNames[pendingPlan.value.name] = pendingCompanyName.value.trim()
    close?.()
    await doCheckout(pendingPlan.value, pendingCompanyName.value.trim())
}

const doCheckout = async (plan, companyName) => {
    if (!plan.stripe_price_id) {
        toast.error(__('This plan is not configured for payment yet'))
        return
    }

    checkingOut.value = plan.name
    try {
        const result = await call('lms.lms.ceu_stripe.create_subscription_checkout', {
            plan_name: plan.name,
            stripe_price_id: plan.stripe_price_id,
            user_email: user.data.email,
            company_name: companyName,
        })
        window.location.href = result.url
    } catch (err) {
        toast.error(err.messages?.[0] || __('Unable to start checkout'))
        checkingOut.value = null
    }
}

usePageMeta(() => ({
    title: __('Membership Plans'),
    icon: brand.favicon,
}))
</script>
