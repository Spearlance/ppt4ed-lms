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
        <div class="p-5 pb-10 max-w-4xl mx-auto">
            <div class="text-center mb-8">
                <h1 class="text-2xl font-bold text-ink-gray-9">
                    {{ __('Choose Your Plan') }}
                </h1>
                <p class="text-ink-gray-5 mt-2">
                    {{ __('Get access to CEU courses with a membership plan') }}
                </p>
            </div>

            <div v-if="plans.data" class="grid md:grid-cols-2 gap-6">
                <div
                    v-for="plan in plans.data"
                    :key="plan.name"
                    class="border rounded-lg p-6 flex flex-col"
                    :class="plan.plan_type === 'Company' ? 'border-blue-300 bg-surface-blue-2' : 'border-outline-gray-3'"
                >
                    <div class="flex items-center justify-between mb-2">
                        <h2 class="text-lg font-semibold text-ink-gray-9">
                            {{ plan.title }}
                        </h2>
                        <Badge :theme="plan.plan_type === 'Company' ? 'blue' : 'green'">
                            {{ plan.plan_type }}
                        </Badge>
                    </div>
                    <div class="text-2xl font-bold text-ink-gray-9 mb-1">
                        ${{ plan.price }}
                        <span class="text-sm font-normal text-ink-gray-5">/year</span>
                    </div>
                    <div class="text-sm text-ink-gray-5 mb-4">
                        {{ plan.ceu_hours }} CEU hours included
                    </div>

                    <div v-if="plan.plan_type === 'Company'" class="mb-4">
                        <FormControl
                            v-model="companyNames[plan.name]"
                            :label="__('Company Name')"
                            placeholder="Your Company Name"
                            type="text"
                        />
                    </div>

                    <Button
                        class="mt-auto w-full"
                        variant="solid"
                        :loading="checkingOut === plan.name"
                        @click="startCheckout(plan)"
                    >
                        {{ plan.plan_type === 'Company' ? __('Start Company Plan') : __('Start Professional Plan') }}
                    </Button>
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
    </div>
</template>

<script setup>
import { Badge, Breadcrumbs, Button, createResource, Dialog, FormControl, toast, usePageMeta, call } from 'frappe-ui'
import { inject, reactive, ref } from 'vue'
import { sessionStore } from '@/stores/session'

const user = inject('$user')
const { brand } = sessionStore()
const checkingOut = ref(null)
const companyNames = reactive({})
const showCompanyDialog = ref(false)
const pendingCompanyName = ref('')
const pendingPlan = ref(null)

const plans = createResource({
    url: 'lms.lms.api.get_membership_plans',
    auto: true,
})

const startCheckout = async (plan) => {
    if (!user?.data?.name) {
        window.location.href = `/login?redirect-to=/lms/membership-plans`
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
        const result = await call('lms.lms.lms.ceu_stripe.create_subscription_checkout', {
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
