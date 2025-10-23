import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PopupPmsComponent } from './popup-pms.component';

describe('PopupPmsComponent', () => {
  let component: PopupPmsComponent;
  let fixture: ComponentFixture<PopupPmsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ PopupPmsComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(PopupPmsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
