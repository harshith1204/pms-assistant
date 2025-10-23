import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SettingPmsComponent } from './setting-pms.component';

describe('SettingPmsComponent', () => {
  let component: SettingPmsComponent;
  let fixture: ComponentFixture<SettingPmsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ SettingPmsComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(SettingPmsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
