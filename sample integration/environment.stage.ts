// This file can be replaced during build by using the `fileReplacements` array.
// `ng build` replaces `environment.ts` with `environment.prod.ts`.
// The list of file replacements can be found in `angular.json`.

export const environment = {
  production: false,
  envName: 'stage',
  // baseUrl:'https://api.simpo.ai/',
  baseUrl: 'https://stage-api.simpo.ai/',
  baseBusinessUrl: "https://stage-business.simpo.ai/",
  businessWithOutGateway: 'https://stage-business.simpo.ai/',
  ecommerceWithoutGateway: 'https://stage-ecommerce.simpo.ai/',
  aiAgentsUrl: 'https://stage-businessrecommendations.simpo.ai/',
  aiTemplateServiceUrl: 'https://stage-aiplanboard.simpo.ai/',
  aiBlogSocketUrl: 'wss://stage-blog.simpo.ai/api/v1/agent/',
  appointementUrl : "https://stage-appointment.simpo.ai/",
  aiPostSocketUrl: 'wss://stage-socialmediawriter.simpo.ai/api/v1/agent/',
  passbookBaseUrl : 'https://stage-passbook.simpo.ai/',
  serverIp: 'https://stage-admin.simpo.ai/',
  baseProjectUrl:"https://stage-project.simpo.ai/",
  newServerIp: 'https://stageapi-smm.simpo.ai/',
  // baseUrl: 'http://54.236.197.24:8003/',
  regenerateUrl: 'https://stage-admin.simpo.ai/',
  urlEndingPoint: "stage.simpo.ai",
  redirectingUrl: 'https://stage-web.simpo.ai',
  iframeRelated: 'https://stage-web.simpo.ai',
  redirectingOtherSite: 'https://stage-simpo-main.web.app',
  indexHtmlUrl: `<script src="https://durga250720.github.io/blogs/blogs.js"></script>`,
  aiGeneratingBaseUrl : "https://stage-websitegenerator.simpo.ai/",
  hrmsUrl: 'https://stage-hrms.web.app',
  passbookStorage: {
    sasToken: '?sv=2024-11-04&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2030-05-10T01:10:57Z&st=2025-06-13T17:10:57Z&spr=https,http&sig=S13EFXN4J4DYC7iBfkXNEu3eyvcHFtjj1aV46G667WA%3D',
    accountName: 'passbookapp',
    containerName: 'dev-lagubandhu',
    domainEndPoint: '.stage.passbookapp.in',
    erpEndPoint: '.stagessp.passbookapp.in'
  },
  firebase: {
    // for facebook login test as prateek has access for stage proficon firebase
    apiKey: 'AIzaSyApQ2YPg4Gz7cG567EnpooA_lhqekfKsME',
    authDomain: 'stage-proficornlabs.firebaseapp.com',
    projectId: 'stage-proficornlabs',
    storageBucket: 'stage-proficornlabs.appspot.com',
    messagingSenderId: '801572740852',
    appId: '1:801572740852:web:44e143c44a0dd5c8a588a1',
    measurementId: 'G-MW1VEYQ1KF',
  },
  linkedinRedirectUrl: "https://stage-web.simpo.ai/admin/marketing/list-overview?type=profile",
    linkedinBusinessRedirectUrl: "https://stage-web.simpo.ai/admin/marketing/list-overview?type=page",
   sasToken:
    '?sv=2024-11-04&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2030-05-10T01:10:57Z&st=2025-06-13T17:10:57Z&spr=https,http&sig=S13EFXN4J4DYC7iBfkXNEu3eyvcHFtjj1aV46G667WA%3D',
accountName: 'passbookapp',
containerName: 'dev-lagubandhu',
  //compoonents image uploading
  componentImageUploading: {
    Version: 1.0,
    CredentialsProvider: {
      CognitoIdentity: {
        Default: {
          PoolId: 'us-east-1:d4bc770a-5664-4051-bd66-6861a6efbd9c',
          Region: 'us-east-1',
        },
      },
    },
    IdentityManager: {
      Default: {},
    },
    S3TransferUtility: {
      Default: {
        Bucket: 'dev-beeos',
        Region: 'us-east-1',
      },
    },
  },

  //mapBox for google maps
  mapbox: {
    accessToken:
      'pk.eyJ1IjoibmFpZHUyNTA3IiwiYSI6ImNsZWxjcGlmZTB0ejkzb3BnMndzbmthM2cifQ.BJoCPnd81NYvx_2VUadF2w',
  },

  cmisFileUpload: {
    sasToken: 'sv=2022-11-02&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2029-12-31T23:45:03Z&st=2024-12-18T15:45:03Z&spr=https,http&sig=Qjj5Xe5KiMxvETm6rP%2FZP31i3xDS9t1QuyuKgcY%2FPC8%3D',
    accountName: 'cmisprod',
    containerName: 'prod-cmis'
  },


  //goDaddy SSO Key for dev environment
  goDaddy: {
    ssoKey:
      'sso-key 3mM44UcgzgNc8W_PW9i1fz5K8SYbVT1Mzg1i:PW2vd4zTxF8orAqBYD9VXs',
  },
  // Unsplash access key
  unsplash: {
    UNSPLASH_API_TOKEN: 'iMn43HCZ_FLCMWkZgUtMAjt-p-M6vmaB1Z_3fbetmJA',
  },
  // Shutterstock access key
  shutterstock: {
    SHUTTERSTOCK_API_TOKEN:
      'v2/a2FzcG9FMmlOSnJLRUZsa2gzU01GMFlyS1R4T0RqRkYvNDIwNDgwNjc3L2N1c3RvbWVyLzQvSU1KUHlFRTUwc01rTE95NTJXbDJJWVk4MU5UVGtlN2cwcHVoaEptaUhQVXZCSXZHNExrVVdzR3lXWkVaTXQ1WkRTQ2pkZXJOSEV2Q21sRWpFdFdIRWRBSkFqUzlFa25LTkkxd3FaTFdscENSTUpTZEMwdWtBVXFIS0ZWN3Nnekd6eGRnbElUMnhpeG43TXJ3UXR4Mk8xT0R6TzJQVExES3A1cUdDaXB3UGwwOTZEMVk2MEJkRmJoc21feDItdGpiZGFwQVExOWNwLUw4RVN5RnZzY0V6US94cExqQi1YZDhubE9JVEdITlJySTNR'
  },
};

/*
 * For easier debugging in development mode, you can import the following file
 * to ignore zone related error stack frames such as `zone.run`, `zoneDelegate.invokeTask`.
 *
 * This import should be commented out in production mode because it will have a negative impact
 * on performance if an error is thrown.
 */
// import 'zone.js/plugins/zone-error';  // Included with Angular CLI.
