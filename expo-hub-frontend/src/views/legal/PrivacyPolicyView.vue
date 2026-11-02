<script setup lang="ts">
// 2026-10-19 合规：隐私政策公开页（注册页勾选同意后跳转阅读）
// 只描述平台实际采集/使用/保存的信息与可执行的权利路径，不引用具体法条编号、不做能力外的承诺
const effectiveDate = '2026-10-19'
const contactEmail = 'admin@expohub.com'
</script>

<template>
  <div>
    <div class="container page-wrapper legal-page">
      <h1 class="page-title">隐私政策</h1>
      <p class="legal-meta">生效日期：{{ effectiveDate }} · 适用平台：ExpoHub</p>

      <div class="card mb-4">
        <div class="card-body">
          <p class="legal-intro">
            ExpoHub 是展会信息与撮合服务提供者，展会由平台运营。
            我们只为提供展会信息浏览、报名购票、供需撮合与站内消息等服务收集必要信息，并按下述方式使用与保护。
            本政策与《用户协议》同时适用；注册时勾选同意，即表示你已阅读并理解这两份文件。
          </p>
        </div>
      </div>

      <div class="card mb-4">
        <div class="card-body legal-section">
          <h2>1. 我们收集什么</h2>
          <ul>
            <li>
              <strong>你主动提供的信息：</strong>
              注册时的用户名、邮箱、密码；选填的手机号、昵称、头像、性别、公司、职位、个人简介；
              展商身份的选填信息，如公司名称、营业执照图片、行业领域、所在地区。
            </li>
            <li>
              <strong>使用服务时产生的信息：</strong>
              账号角色（visitor / buyer / exhibitor / admin）、展会报名与购票记录、收藏、采购需求、
              展品与展位信息、站内消息、积分与邀请码记录。
            </li>
            <li>
              <strong>设备与日志信息：</strong>
              访问时间、IP 地址、浏览器类型、访问页面等，用于账号安全、故障排查与服务稳定性分析。
            </li>
            <li>
              <strong>同意记录：</strong>
              你同意本政策与《用户协议》的时间，作为同意凭据留存。
            </li>
          </ul>
          <p class="legal-note">
            我们不收集身份证号、银行卡号、精确行踪等与展会服务无关的敏感个人信息。
            如后续因业务确需收集，我们会先说明用途并取得你的单独同意。
          </p>
        </div>
      </div>

      <div class="card mb-4">
        <div class="card-body legal-section">
          <h2>2. 用途</h2>
          <ul>
            <li><strong>账号与登录：</strong>创建账号、验证身份、找回密码、区分访客/买家/展商等不同角色的功能权限。</li>
            <li><strong>展会服务：</strong>完成展会报名、购票与现场核销，向展商分配展位、展示展品。</li>
            <li><strong>撮合与消息：</strong>按你填写的行业领域、地区、采购需求，向你推荐相关展会、展商与采购需求；支持站内消息沟通。</li>
            <li><strong>安全与风控：</strong>识别异常登录、刷积分、批量抓取等行为，处理投诉与纠纷。</li>
            <li><strong>服务通知：</strong>发送报名成功、审核结果、展会变更等与你的操作直接相关的通知。</li>
            <li><strong>依法配合：</strong>按有权机关的要求提供必要信息。</li>
          </ul>
          <p class="legal-note">
            我们不会将你的信息用于与上述目的无关的场景，也不会出售你的个人信息。
            仅在为你提供服务所必需（如服务器托管、图片存储、短信通知）、取得你的同意或法律法规要求时，
            才会与相应服务商共享必要信息，并要求其履行保密义务。
          </p>
        </div>
      </div>

      <div class="card mb-4">
        <div class="card-body legal-section">
          <h2>3. 存储与期限</h2>
          <ul>
            <li><strong>存储方式：</strong>信息存储于平台运营的服务器；密码仅以不可逆的哈希形式保存，平台不保存明文密码。</li>
            <li><strong>保留期限：</strong>账号信息在账号存续期间保留；账号注销后删除或作匿名化处理。</li>
            <li><strong>必要留存：</strong>报名、票务、积分等记录在法律法规要求或处理争议所必需的期限内保留，期满后删除或匿名化。</li>
            <li><strong>安全措施：</strong>采用密码哈希、按角色的访问权限控制、操作日志留存等措施；如发生信息安全事件，我们会尽快排查并通过站内通知或邮件告知受影响的用户。</li>
            <li><strong>跨境提供：</strong>如确需向境外提供你的个人信息，我们会单独告知并提供相应保护措施，依法取得你的同意。</li>
          </ul>
        </div>
      </div>

      <div class="card mb-4">
        <div class="card-body legal-section">
          <h2>4. 你的权利（查阅 / 更正 / 删除 / 撤回 / 注销）</h2>
          <ul>
            <li><strong>查阅与复制：</strong>登录后可在「个人中心」查看账号资料；如需更完整的副本，可按第 5 节方式提出。</li>
            <li><strong>更正：</strong>可在「账号设置」修改邮箱、手机、公司等信息；无法自行修改的字段可联系我们更正。</li>
            <li><strong>删除：</strong>对超出服务必要范围、或你不再使用而无需保留的信息，可要求删除。</li>
            <li><strong>撤回同意：</strong>你可随时撤回对本政策的同意；撤回不影响撤回前已进行的处理，但可能导致部分功能不可用（例如无法完成注册或登录）。</li>
            <li><strong>注销账号：</strong>可按第 5 节方式提交注销申请，我们核验身份后处理；注销后账号不可恢复，相关权益与记录将按第 3 节处理。</li>
            <li><strong>个性化推荐开关：</strong>推荐默认依据你的行业领域与兴趣标签；可在「账号设置 → 推荐与标签」中随时关闭，关闭后推荐与匹配结果改为按最新内容排序，不再使用你的画像信息。</li>
            <li><strong>未成年人：</strong>本平台面向企业与行业从业者，不面向未成年人提供服务；如你未满 18 周岁，请在监护人指导下使用。</li>
            <li><strong>响应时限：</strong>我们在收到请求并核验身份后 15 个工作日内答复；情形复杂的，会说明原因并告知预计处理时间。</li>
          </ul>
        </div>
      </div>

      <div class="card mb-4">
        <div class="card-body legal-section">
          <h2>5. 联系方式</h2>
          <ul>
            <li><strong>邮箱：</strong>{{ contactEmail }}</li>
            <li><strong>如何提交：</strong>请使用注册邮箱发送邮件，标题注明「隐私政策-查阅/更正/删除/撤回/注销」，正文写明用户名与具体诉求，便于我们核验身份。</li>
            <li><strong>身份核验：</strong>为防止他人冒用你的账号，我们可能要求你补充可验证的信息；核验通过后即开始处理。</li>
            <li><strong>政策更新：</strong>本政策更新后在本页发布并标注生效日期；涉及你主要权利的变更，我们会通过站内通知或邮件提醒你查看。</li>
          </ul>
          <p class="legal-note">
            本页如有与你实际使用不符之处，欢迎通过上述邮箱指出，我们会核实后修正。
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
