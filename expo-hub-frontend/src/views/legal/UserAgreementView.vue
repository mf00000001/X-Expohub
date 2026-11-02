<script setup lang="ts">
// 2026-10-19 合规：用户协议公开页（注册页勾选同意后跳转阅读）
// 只写平台当前真实提供的服务与规则，不引用具体法条编号、不做能力外的承诺
const effectiveDate = '2026-10-19'
const contactEmail = 'admin@expohub.com'
</script>

<template>
  <div>
    <div class="container page-wrapper legal-page">
      <h1 class="page-title">用户协议</h1>
      <p class="legal-meta">生效日期：{{ effectiveDate }} · 适用平台：ExpoHub</p>

      <div class="card mb-4">
        <div class="card-body">
          <p class="legal-intro">
            欢迎使用 ExpoHub。本协议是你与平台之间的约定，与《隐私政策》一并构成你使用平台服务的完整条件。
            注册时勾选同意，即表示你已阅读并接受本协议；如不同意，请停止注册与使用。
          </p>
        </div>
      </div>

      <div class="card mb-4">
        <div class="card-body legal-section">
          <h2>1. 服务说明</h2>
          <ul>
            <li>
              <strong>平台定位：</strong>
              平台为展会信息与撮合服务提供者；展会由平台运营。
            </li>
            <li>
              <strong>具体服务：</strong>
              展会信息发布与浏览、展会报名与票务、展位与展品展示、采购需求发布与撮合、站内消息、积分等功能。
            </li>
            <li>
              <strong>服务调整：</strong>
              平台可根据业务需要新增、调整或下线部分功能，并通过站内通知或页面公告说明；涉及已付费权益的，会先告知处理方案。
            </li>
            <li>
              <strong>服务可用性：</strong>
              平台会尽力保障服务稳定，但不对服务完全不中断作出承诺。
            </li>
          </ul>
        </div>
      </div>

      <div class="card mb-4">
        <div class="card-body legal-section">
          <h2>2. 账号与使用规则</h2>
          <ul>
            <li>
              <strong>角色与注册：</strong>
              自助注册仅开放 visitor（游客）、buyer（买家）、exhibitor（展商）三种身份；admin（平台运营）账号由平台后台开通，不开放自助注册。
            </li>
            <li>
              <strong>信息真实：</strong>
              注册时须填写真实、可用的邮箱与用户名；以展商身份入驻的，须保证公司名称、营业执照等资质信息真实有效，平台可要求补充证明材料。
            </li>
            <li>
              <strong>账号保管：</strong>
              账号仅限本人使用，不得转让、出借或出售；以你的账号进行的操作视为你本人的行为。发现账号被盗用的，请立即修改密码并按第 5 节方式告知平台。
            </li>
            <li>
              <strong>禁止行为：</strong>
              不得发布虚假的展会、展位、展品或采购信息；不得冒用他人身份或企业名义；
              不得发布违法内容或侵犯他人知识产权、商业秘密的内容；
              不得使用自动化程序批量抓取数据、刷点击或刷积分、绕过权限、干扰服务；
              不得利用站内消息骚扰他人或发送与平台服务无关的广告。
            </li>
            <li>
              <strong>违约处理：</strong>
              对违反上述规则的行为，平台可视情节采取提醒、删除内容、限制功能、暂停或终止账号等措施；你有权提出申诉，平台会复核后答复。
            </li>
          </ul>
        </div>
      </div>

      <div class="card mb-4">
        <div class="card-body legal-section">
          <h2>3. 内容与交易</h2>
          <ul>
            <li>
              <strong>你的内容：</strong>
              你发布的展品、公司介绍、采购需求等内容归你所有；为向其他用户展示与撮合，你授予平台在平台范围内存储、展示、必要排版编辑与推广使用的非独占许可。
            </li>
            <li>
              <strong>平台内容：</strong>
              平台的名称、标识、页面设计与程序代码归平台所有，未经许可不得复制、镜像或作商业使用。
            </li>
            <li>
              <strong>交易关系：</strong>
              平台自营展会的报名与票务由平台提供并负责；展商与采购商之间的具体交易由双方自行协商达成并履行，平台不作为该交易的当事方，也不为该交易提供履约担保。
            </li>
            <li>
              <strong>纠纷协助：</strong>
              双方在平台内发生争议的，可向平台投诉；平台会在信息核实范围内提供记录与沟通协助，但不代替双方作出裁判。
            </li>
          </ul>
        </div>
      </div>

      <div class="card mb-4">
        <div class="card-body legal-section">
          <h2>4. 责任边界</h2>
          <ul>
            <li>
              <strong>信息审核：</strong>
              平台会对展会与展商信息作必要的形式审核，但无法保证用户自行发布的内容完全准确；如发现信息不实，请通过第 5 节方式举报。
            </li>
            <li>
              <strong>不可抗力与第三方原因：</strong>
              因不可抗力、网络与第三方服务异常、计划内维护导致服务中断的，平台会尽快恢复并通过公告说明，但不承担由此产生的间接损失。
            </li>
            <li>
              <strong>你的责任：</strong>
              因你违反本协议或发布不实、侵权内容给平台或第三方造成损失的，你应承担相应责任。
            </li>
          </ul>
        </div>
      </div>

      <div class="card mb-4">
        <div class="card-body legal-section">
          <h2>5. 协议变更、终止与联系方式</h2>
          <ul>
            <li><strong>协议变更：</strong>本协议更新后在本页发布并标注生效日期；涉及你主要权利义务的变更，我们会通过站内通知或邮件提醒你查看。</li>
            <li><strong>终止使用：</strong>你可随时停止使用平台服务，并按《隐私政策》第 5 节的方式申请注销账号；注销后本协议即终止。</li>
            <li><strong>平台终止：</strong>你严重违反本协议的，平台可终止向你提供服务，并说明理由。</li>
            <li><strong>联系方式：</strong>{{ contactEmail }}（请使用注册邮箱发送，写明用户名与具体诉求）。</li>
          </ul>
          <p class="legal-note">
            本协议未约定的事项，以《隐私政策》与平台页面公告为准。
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.legal-page {
  padding-top: 24px;
  padding-bottom: 40px;
  max-width: 860px;
}
.page-title {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}
.legal-meta {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 6px 0 20px;
}
.legal-intro {
  font-size: 14px;
  line-height: 1.9;
  color: var(--text-primary);
}
.legal-section h2 {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
}
.legal-section ul {
  list-style: disc;
  padding-left: 20px;
  margin: 0;
}
.legal-section li {
  font-size: 14px;
  line-height: 1.9;
  color: var(--text-primary);
  margin-bottom: 8px;
}
.legal-section li strong {
  font-weight: 600;
  margin-right: 2px;
}
.legal-note {
  font-size: 13px;
  line-height: 1.8;
  color: var(--text-secondary);
  background: var(--bg-color);
  border-radius: var(--radius-md);
  padding: 10px 14px;
  margin-top: 10px;
}
@media (max-width: 640px) {
  .page-title {
    font-size: 22px;
  }
  .legal-section li {
    font-size: 13px;
  }
}
</style>
